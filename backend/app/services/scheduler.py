"""
scheduler.py
=============

このファイルの役割:
  バックグラウンドで定期的に「データ取得→SMCシグナル判定→
  (必要なら)Discord通知」を繰り返す仕組み。

  4時間足・1時間足・15分足・5分足・1分足の5層構造でSMC分析を行う。
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.database import SessionLocal
from app.core.symbols_config import SYMBOLS
from app.services.twelve_data_client import fetch_time_series, TwelveDataError
from app.services.price_data_service import save_price_data, get_recent_price_data
from app.indicators.technical_indicators import add_all_indicators
from app.services.discord_notifier import send_signal_notification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

NOTIFIABLE_LABELS = {"WEAK", "NORMAL", "STRONG"}
API_REQUEST_INTERVAL_SECONDS = 12


async def _fetch_and_save(symbol: str, timeframe: str) -> None:
    """指定した銘柄・時間足のデータをAPIから取得し、DBに保存する。"""
    from app.core.symbols_config import get_twelve_data_symbol
    twelve_data_symbol = get_twelve_data_symbol(symbol)
    df = await fetch_time_series(twelve_data_symbol, timeframe, output_size=300)
    db = SessionLocal()
    try:
        save_price_data(db, symbol, timeframe, df)
    finally:
        db.close()


async def check_signal_for_symbol(symbol: str) -> None:
    """定期実行のジョブから呼ばれる。"""
    await check_signal_for_symbol_with_result(symbol)


async def check_signal_for_symbol_with_result(symbol: str) -> dict:
    """
    1つの銘柄について、データ取得からSMCシグナル判定・通知までの
    一連の処理を実行し、結果を辞書として返す。
    4時間足・1時間足・15分足・5分足・1分足の5層構造で判定する。
    """
    try:
        # --- 1. データ取得・保存(5時間足対応) ---
        await _fetch_and_save(symbol, "4h")
        await asyncio.sleep(API_REQUEST_INTERVAL_SECONDS)
        await _fetch_and_save(symbol, "1h")
        await asyncio.sleep(API_REQUEST_INTERVAL_SECONDS)
        await _fetch_and_save(symbol, "15m")
        await asyncio.sleep(API_REQUEST_INTERVAL_SECONDS)
        await _fetch_and_save(symbol, "5m")
        await asyncio.sleep(API_REQUEST_INTERVAL_SECONDS)
        await _fetch_and_save(symbol, "1m")

        # --- 2. DBから読み込む ---
        db = SessionLocal()
        try:
            df_4h = get_recent_price_data(db, symbol, "4h", limit=200)
            df_1h = get_recent_price_data(db, symbol, "1h", limit=300)
            df_15m = get_recent_price_data(db, symbol, "15m", limit=300)
            df_5m = get_recent_price_data(db, symbol, "5m", limit=300)
            df_1m = get_recent_price_data(db, symbol, "1m", limit=300)
        finally:
            db.close()

        if df_4h.empty or df_1h.empty or df_15m.empty or df_5m.empty:
            logger.warning(f"[scheduler] {symbol}: データが不足しているためスキップします")
            return {"symbol": symbol, "status": "error", "message": "データが不足しています"}

        df_5m_with_indicators = add_all_indicators(df_5m)

        # --- 3. SMCシグナル判定(5時間足対応) ---
        from app.strategies.smc_signal_generator import generate_smc_signal
        result = generate_smc_signal(
            df_4h, df_1h, df_15m, df_5m_with_indicators, symbol,
            df_1m=df_1m if not df_1m.empty else None
        )

        logger.info(
            f"[scheduler] {symbol}: signal={result.signal_type} "
            f"score={result.score} label={result.strength_label}"
        )

        # --- 4. WEAK以上なら通知 ---
        notified = False
        if result.strength_label in NOTIFIABLE_LABELS:
            notified = await send_signal_notification(symbol, result)

        return {
            "symbol": symbol,
            "status": "ok",
            "higher_tf_trend": result.reasons.get("market_structure_4h", ""),
            "signal_type": result.signal_type,
            "score": result.score,
            "strength_label": result.strength_label,
            "entry_price": result.entry_price,
            "atr_value": result.atr_value,
            "reasons": result.reasons,
            "discord_notified": notified,
        }

    except TwelveDataError as e:
        logger.error(f"[scheduler] {symbol}: Twelve Data APIエラー: {e}")
        return {"symbol": symbol, "status": "error", "message": f"Twelve Data APIエラー: {e}"}
    except Exception as e:
        logger.exception(f"[scheduler] {symbol}: 予期しないエラーが発生しました: {e}")
        return {"symbol": symbol, "status": "error", "message": f"予期しないエラー: {e}"}


async def check_all_symbols() -> None:
    """すべての銘柄についてシグナルチェックを実行する。"""
    symbol_list = list(SYMBOLS.keys())
    for i, symbol in enumerate(symbol_list):
        await check_signal_for_symbol(symbol)
        if i < len(symbol_list) - 1:
            await asyncio.sleep(API_REQUEST_INTERVAL_SECONDS)


def start_scheduler() -> AsyncIOScheduler:
    """スケジューラを開始する。"""
    from app.core.config import settings

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_all_symbols,
        "interval",
        seconds=settings.POLLING_INTERVAL_SECONDS,
        id="check_all_symbols_job",
    )
    scheduler.start()
    logger.info(
        f"[scheduler] スケジューラを開始しました "
        f"(間隔: {settings.POLLING_INTERVAL_SECONDS}秒)"
    )
    return scheduler
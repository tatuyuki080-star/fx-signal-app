"""
scheduler.py
=============

このファイルの役割:
  バックグラウンドで定期的に「データ取得→指標計算→シグナル判定→
  (必要なら)Discord通知」を繰り返す仕組み。

なぜ必要?:
  これまでの /debug/... エンドポイントは、人がブラウザでURLを開かないと
  実行されなかった。実運用では「アプリを起動しておけば自動でシグナルを
  チェックしてくれる」状態が必要なため、定期実行の仕組みを用意する。

使うライブラリ:
  APScheduler (Advanced Python Scheduler)
  Pythonでcronのような定期実行を簡単に書けるライブラリ。

通知の方針:
  strength_label が "WEAK" 以上(スコア50点以上)のときだけDiscordに通知する。
  NO_TRADE(NONE)のときは通知しない(無駄な通知でユーザーが疲弊しないため)。

使い方(main.pyから):
  from app.services.scheduler import start_scheduler
  start_scheduler()  # FastAPI起動時に呼ぶ
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.database import SessionLocal
from app.core.symbols_config import SYMBOLS, SIGNAL_TIMEFRAMES
from app.services.twelve_data_client import fetch_time_series, TwelveDataError
from app.services.price_data_service import save_price_data, get_recent_price_data
from app.indicators.technical_indicators import add_all_indicators
from app.strategies.trend_analyzer import analyze_higher_timeframe_trend
from app.strategies.signal_generator import generate_signal
from app.services.discord_notifier import send_signal_notification

# このアプリ全体のログを標準出力(docker compose up のログ)に表示するための設定。
# basicConfig は一度呼ばれればそれ以降のlogger.info()等が画面に出るようになる。
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

# WEAK以上(60点以上)のときだけ通知する
NOTIFIABLE_LABELS = {"WEAK", "NORMAL", "STRONG"}

# Twelve Dataの無料プラン(1分あたり8リクエスト)を超えないよう、
# 1つのAPIリクエストごとに待機する秒数。
# 1分(60秒) / 8リクエスト = 7.5秒なので、安全マージンを取って8秒にしている。
API_REQUEST_INTERVAL_SECONDS = 8


async def _fetch_and_save(symbol: str, timeframe: str) -> None:
    """
    指定した銘柄・時間足のデータをAPIから取得し、DBに保存する。
    内部のtwelve_data_symbol変換も含めて、1つの処理にまとめている。
    """
    from app.core.symbols_config import get_twelve_data_symbol

    twelve_data_symbol = get_twelve_data_symbol(symbol)
    df = await fetch_time_series(twelve_data_symbol, timeframe, output_size=300)

    db = SessionLocal()
    try:
        save_price_data(db, symbol, timeframe, df)
    finally:
        db.close()


async def check_signal_for_symbol(symbol: str) -> None:
    """
    1つの銘柄について、データ取得からシグナル判定・通知までの
    一連の処理を実行する(定期実行のジョブから呼ばれる)。
    結果を返す必要がない場合はこちらを使う。
    """
    await check_signal_for_symbol_with_result(symbol)


async def check_signal_for_symbol_with_result(symbol: str) -> dict:
    """
    1つの銘柄について、データ取得からシグナル判定・通知までの
    一連の処理を実行し、結果を辞書として返す。

    check_signal_for_symbol() との違い:
      こちらは結果(シグナル種別・スコアなど)を呼び出し元に返す。
      /debug/run-now のような「今すぐ結果を確認したい」用途で使う。

    処理の流れ:
      1. 1時間足(上位足)のデータを取得・保存
      2. 5分足(エントリー判定用)のデータを取得・保存
      3. 指標を計算し、上位足トレンドとシグナルを判定
      4. スコアがWEAK以上ならDiscordに通知

    注意:
      この関数内のエラーは外には投げず、結果辞書の中にエラー情報を
      含めて返す。1つの銘柄の処理が失敗しても、他の銘柄のチェックには
      影響させないようにするため。
    """
    try:
        # --- 1. データ取得・保存 ---
        # 各APIリクエストの間に待機時間を入れて、レート制限(1分8リクエスト)を回避する
        await _fetch_and_save(symbol, "1h")
        await asyncio.sleep(API_REQUEST_INTERVAL_SECONDS)
        await _fetch_and_save(symbol, "5m")

        # --- 2. DBから読み込んで指標計算 ---
        db = SessionLocal()
        try:
            df_1h = get_recent_price_data(db, symbol, "1h", limit=300)
            df_entry = get_recent_price_data(db, symbol, "5m", limit=300)
        finally:
            db.close()

        if df_1h.empty or df_entry.empty:
            logger.warning(f"[scheduler] {symbol}: データが不足しているためスキップします")
            return {"symbol": symbol, "status": "error", "message": "データが不足しています"}

        df_1h_with_indicators = add_all_indicators(df_1h)
        df_entry_with_indicators = add_all_indicators(df_entry)

        # --- 3. シグナル判定 ---
        trend_direction = analyze_higher_timeframe_trend(df_1h_with_indicators)
        result = generate_signal(df_entry_with_indicators, trend_direction, symbol)

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
            "higher_tf_trend": trend_direction.value,
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
    """
    対応するすべての銘柄についてシグナルチェックを実行する。
    各銘柄は順番に処理し、銘柄間にも待機時間を入れる
    (Twelve Dataの無料プランのレート制限[1分あたり8リクエスト]を考慮)。
    """
    symbol_list = list(SYMBOLS.keys())
    for i, symbol in enumerate(symbol_list):
        await check_signal_for_symbol(symbol)
        # 最後の銘柄の後は待機不要
        if i < len(symbol_list) - 1:
            await asyncio.sleep(API_REQUEST_INTERVAL_SECONDS)


def start_scheduler() -> AsyncIOScheduler:
    """
    スケジューラを開始する。FastAPIの起動時に呼び出す想定。

    実行間隔:
      settings.POLLING_INTERVAL_SECONDS (.envで設定、デフォルト300秒=5分)
      ごとに check_all_symbols() を実行する。

    戻り値:
      起動したスケジューラのインスタンス(main.py側で保持しておくと、
      終了時に停止させることができる)。
    """
    from app.core.config import settings

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_all_symbols,
        "interval",
        seconds=settings.POLLING_INTERVAL_SECONDS,
        id="check_all_symbols_job",
        # next_run_time は指定しない。intervalトリガーのデフォルト動作により、
        # 「起動時刻 + 間隔(秒)」が自動的に最初の実行時刻として設定される。
    )
    scheduler.start()
    logger.info(
        f"[scheduler] スケジューラを開始しました "
        f"(間隔: {settings.POLLING_INTERVAL_SECONDS}秒)"
    )
    return scheduler
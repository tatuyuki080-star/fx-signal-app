"""
signals.py (api/)
==================

このファイルの役割:
  フロントエンドから呼ばれる、シグナル関連の正式なAPIエンドポイント。
  SMCベースのシグナルロジックを使用する。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.symbols_config import SYMBOLS
from app.services.price_data_service import get_recent_price_data
from app.indicators.technical_indicators import add_all_indicators
from app.indicators.smc_analyzer import analyze_smc
from app.strategies.smc_signal_generator import generate_smc_signal
from app.services.ai_analyzer import analyze_signal_with_ai

router = APIRouter(prefix="/api", tags=["signals"])


@router.get("/symbols")
def list_symbols():
    """対応している銘柄の一覧を返す。"""
    return [
        {
            "symbol": symbol,
            "display_name": info["display_name"],
            "category": info["category"],
        }
        for symbol, info in SYMBOLS.items()
    ]


@router.get("/signals/{symbol}")
async def get_latest_signal(symbol: str, db: Session = Depends(get_db)):
    """
    指定した銘柄の最新SMCシグナルを計算して返す。
    """
    if symbol not in SYMBOLS:
        raise HTTPException(
            status_code=404, detail=f"未対応の銘柄です: {symbol}"
        )

    # 1時間足データ取得(市場構造判定用)
    df_1h = get_recent_price_data(db, symbol, "1h", limit=300)
    # 5分足データ取得(エントリー判定用)
    df_5m = get_recent_price_data(db, symbol, "5m", limit=300)

    if df_1h.empty or df_5m.empty:
        raise HTTPException(
            status_code=404,
            detail=f"{symbol} のデータがまだありません。",
        )

    # ATR計算のために指標を追加
    df_5m = add_all_indicators(df_5m)

    # SMCシグナル生成
    result = generate_smc_signal(df_1h, df_5m, symbol)

    # AI分析
    ai_analysis = await analyze_signal_with_ai(
        symbol=symbol,
        signal_type=result.signal_type,
        score=result.score,
        strength_label=result.strength_label,
        higher_tf_trend=result.reasons.get("market_structure", ""),
        reasons=result.reasons,
        entry_price=result.entry_price,
        stop_loss=result.stop_loss,
        take_profit=result.take_profit,
        atr_value=result.atr_value,
    )

    return {
        "symbol": symbol,
        "signal_type": result.signal_type,
        "score": result.score,
        "strength_label": result.strength_label,
        "entry_price": result.entry_price,
        "stop_loss": result.stop_loss,
        "take_profit": result.take_profit,
        "atr_value": result.atr_value,
        "reasons": result.reasons,
        "ai_analysis": ai_analysis,
    }
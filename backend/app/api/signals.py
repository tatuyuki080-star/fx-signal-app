"""
signals.py (api/)
==================

このファイルの役割:
  フロントエンドから呼ばれる、シグナル関連の正式なAPIエンドポイント。

なぜ main.py から分離する?:
  main.py に全エンドポイントを書き続けると、機能が増えるたびに
  ファイルが肥大化し、見通しが悪くなる。FastAPIの「APIRouter」を使うと、
  関連するエンドポイントをファイル単位でまとめ、main.py 側では
  「読み込んで登録する」だけで済むようになる。

このファイルが提供するエンドポイント:
  GET /api/symbols              : 対応銘柄の一覧を返す
  GET /api/signals/{symbol}     : 指定銘柄の最新シグナルを返す
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.symbols_config import SYMBOLS
from app.services.price_data_service import get_recent_price_data
from app.indicators.technical_indicators import add_all_indicators
from app.strategies.trend_analyzer import analyze_higher_timeframe_trend
from app.strategies.signal_generator import generate_signal

router = APIRouter(prefix="/api", tags=["signals"])


@router.get("/symbols")
def list_symbols():
    """
    対応している銘柄の一覧を返す。

    フロントエンドの銘柄選択タブなどで使う。

    戻り値の例:
      [
        {"symbol": "USDJPY", "display_name": "USD/JPY", "category": "forex"},
        ...
      ]
    """
    return [
        {
            "symbol": symbol,
            "display_name": info["display_name"],
            "category": info["category"],
        }
        for symbol, info in SYMBOLS.items()
    ]


@router.get("/signals/{symbol}")
def get_latest_signal(symbol: str, db: Session = Depends(get_db)):
    """
    指定した銘柄の最新シグナルを計算して返す。

    引数:
      symbol: アプリ内表記。例: "USDJPY"(URLパスの一部として渡される)

    戻り値の例:
      {
        "symbol": "USDJPY",
        "higher_tf_trend": "UPTREND",
        "signal_type": "NO_TRADE",
        "score": 40.0,
        "strength_label": "NONE",
        "entry_price": 162.43,
        "atr_value": 0.042,
        "reasons": {...}
      }

    注意:
      ここではDBにすでに保存されている直近データから計算する。
      最新のAPIデータを取得し直すわけではない
      (それはバックグラウンドのスケジューラが担当する役割)。
    """
    if symbol not in SYMBOLS:
        raise HTTPException(status_code=404, detail=f"未対応の銘柄です: {symbol}")

    df_1h = get_recent_price_data(db, symbol, "1h", limit=300)
    df_entry = get_recent_price_data(db, symbol, "5m", limit=300)

    if df_1h.empty or df_entry.empty:
        raise HTTPException(
            status_code=404,
            detail=f"{symbol} のデータがまだありません。スケジューラの初回実行をお待ちください。",
        )

    df_1h_with_indicators = add_all_indicators(df_1h)
    df_entry_with_indicators = add_all_indicators(df_entry)

    trend_direction = analyze_higher_timeframe_trend(df_1h_with_indicators)
    result = generate_signal(df_entry_with_indicators, trend_direction, symbol)

    return {
        "symbol": symbol,
        "higher_tf_trend": trend_direction.value,
        "signal_type": result.signal_type,
        "score": result.score,
        "strength_label": result.strength_label,
        "entry_price": result.entry_price,
        "atr_value": result.atr_value,
        "reasons": result.reasons,
    }
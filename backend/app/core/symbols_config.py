"""
symbols_config.py
==================

このファイルの役割:
  対応銘柄の一覧と、銘柄ごとに異なる設定値(API表記の変換、ATR閾値など)
  をまとめて管理する。
"""

SYMBOLS = {
    "XAUUSD": {
        "twelve_data_symbol": "XAU/USD",
        "display_name": "GOLD (XAU/USD)",
        "category": "commodity",
        "atr_min_threshold": 0.30,
    },
}

TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h"]
SIGNAL_TIMEFRAMES = ["5m", "15m", "1h", "4h"]
CHART_ONLY_TIMEFRAMES = ["1m"]


def get_twelve_data_symbol(symbol: str) -> str:
    if symbol not in SYMBOLS:
        raise KeyError(f"未対応の銘柄です: {symbol}")
    return SYMBOLS[symbol]["twelve_data_symbol"]


def get_atr_threshold(symbol: str) -> float:
    if symbol not in SYMBOLS:
        raise KeyError(f"未対応の銘柄です: {symbol}")
    return SYMBOLS[symbol]["atr_min_threshold"]
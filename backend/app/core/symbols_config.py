"""
symbols_config.py
==================

このファイルの役割:
  対応銘柄の一覧と、銘柄ごとに異なる設定値(API表記の変換、ATR閾値など)
  をまとめて管理する。
"""

SYMBOLS = {
    "USDJPY": {
        "twelve_data_symbol": "USD/JPY",
        "display_name": "USD/JPY",
        "category": "forex",
        "atr_min_threshold": 0.03,
    },
    "EURUSD": {
        "twelve_data_symbol": "EUR/USD",
        "display_name": "EUR/USD",
        "category": "forex",
        "atr_min_threshold": 0.0003,
    },
    "GBPJPY": {
        "twelve_data_symbol": "GBP/JPY",
        "display_name": "GBP/JPY",
        "category": "forex",
        "atr_min_threshold": 0.05,
    },
    "XAUUSD": {
        "twelve_data_symbol": "XAU/USD",
        "display_name": "GOLD (XAU/USD)",
        "category": "commodity",
        # GOLDはFXペアよりボラティリティの絶対値が大きいため閾値も大きくする
        "atr_min_threshold": 0.30,
    },
    # 注意: XAGUSD(Silver)はTwelve Dataの無料プランでは取得できない
    # ("This symbol is available starting with the Grow or Venture plan" という
    #  404エラーが返る)ため、対応銘柄から除外している。
    # 将来的に有料プランへの移行や別APIとの併用を検討する場合は、
    # ここに "XAGUSD" を追加すれば対応できる設計にしてある。
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
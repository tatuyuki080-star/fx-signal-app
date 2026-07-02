"""
trend_analyzer.py
==================

このファイルの役割:
  上位足(1時間足)のトレンド方向を判定する。

なぜ上位足判定を分離する?:
  要件の「上位足優先・順張り中心」という思想を実現するため、
  「大きな流れ(1時間足)に逆らうエントリーをしない」というルールを
  signal_generator.py の判定の"前提条件"として独立させている。
  ここの判定結果が NEUTRAL なら、そもそも BUY/SELL のシグナルを
  出すこと自体ができない(エントリー禁止)。

判定ルール:
  BUY許可 (UPTREND):
    1時間足で SMA20 > SMA50 かつ 価格(close) > SMA200
  SELL許可 (DOWNTREND):
    1時間足で SMA20 < SMA50 かつ 価格(close) < SMA200
  どちらにも当たらない場合は NEUTRAL(どちらにもエントリーしない)

使い方(他のファイルから):
  from app.strategies.trend_analyzer import analyze_higher_timeframe_trend
  trend = analyze_higher_timeframe_trend(df_1h_with_indicators)
"""

from enum import Enum
import pandas as pd


class TrendDirection(str, Enum):
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    NEUTRAL = "NEUTRAL"


def analyze_higher_timeframe_trend(df_1h: pd.DataFrame) -> TrendDirection:
    """
    1時間足の指標データから、上位足トレンド方向を判定する。

    引数:
      df_1h: indicators/technical_indicators.py の add_all_indicators() を
             適用済みの1時間足DataFrame(SMA_20, SMA_50, SMA_200列を含む)

    戻り値:
      TrendDirection.UPTREND   : BUYエントリーが許可される上昇トレンド
      TrendDirection.DOWNTREND : SELLエントリーが許可される下降トレンド
      TrendDirection.NEUTRAL   : どちらの条件にも該当しない(エントリー禁止)

    注意:
      SMA_200 はデータ本数が200本未満だと NaN になる。
      その場合、判定材料が不足しているため安全側に倒して NEUTRAL を返す。
    """
    if df_1h.empty:
        return TrendDirection.NEUTRAL

    latest = df_1h.iloc[-1]

    sma20 = latest.get("SMA_20")
    sma50 = latest.get("SMA_50")
    sma200 = latest.get("SMA_200")
    close = latest.get("close")

    if pd.isna(sma20) or pd.isna(sma50) or pd.isna(sma200) or pd.isna(close):
        return TrendDirection.NEUTRAL

    if sma20 > sma50 and close > sma200:
        return TrendDirection.UPTREND

    if sma20 < sma50 and close < sma200:
        return TrendDirection.DOWNTREND

    return TrendDirection.NEUTRAL
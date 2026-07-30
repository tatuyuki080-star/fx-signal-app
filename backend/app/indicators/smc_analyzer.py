"""
smc_analyzer.py
================

このファイルの役割:
  SMC(Smart Money Concept)の主要概念を計算する。

  計算する要素:
    1. スイング高値・安値(Swing High/Low)
    2. 市場構造(HH/HL/LH/LL)
    3. BOS(Break of Structure) / CHOCH(Change of Character)
    4. オーダーブロック(Order Block)
    5. 需給ゾーン(Supply/Demand Zone)
    6. FVG(Fair Value Gap)

設計方針:
  - DataFrameを受け取り、SMC情報を返す
  - DBアクセスやAPI呼び出しは一切行わない
  - 純粋な計算ロジックのみ
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# データ構造
# ============================================================

@dataclass
class SwingPoint:
    """スイング高値・安値の情報"""
    index: int
    price: float
    swing_type: str  # "high" or "low"


@dataclass
class MarketStructure:
    """市場構造の情報"""
    trend: str = "neutral"  # "bullish" / "bearish" / "neutral"
    last_swing_high: Optional[float] = None
    last_swing_low: Optional[float] = None
    bos_detected: bool = False
    bos_direction: str = ""
    choch_detected: bool = False
    choch_direction: str = ""


@dataclass
class OrderBlock:
    """オーダーブロックの情報"""
    ob_type: str  # "bullish" / "bearish"
    top: float
    bottom: float
    index: int
    is_active: bool = True


@dataclass
class SupplyDemandZone:
    """需給ゾーンの情報"""
    zone_type: str  # "supply" / "demand"
    top: float
    bottom: float
    index: int
    is_active: bool = True


@dataclass
class FairValueGap:
    """フェアバリューギャップの情報"""
    fvg_type: str  # "bullish" / "bearish"
    top: float
    bottom: float
    index: int
    is_filled: bool = False


@dataclass
class SMCAnalysis:
    """SMC分析の全結果をまとめたデータ構造"""
    market_structure: MarketStructure = field(
        default_factory=MarketStructure
    )
    order_blocks: list = field(default_factory=list)
    supply_demand_zones: list = field(default_factory=list)
    fair_value_gaps: list = field(default_factory=list)
    swing_highs: list = field(default_factory=list)
    swing_lows: list = field(default_factory=list)


# ============================================================
# スイング高値・安値の検出
# ============================================================

def detect_swing_points(
    df: pd.DataFrame, swing_length: int = 10
) -> tuple:
    """
    スイング高値・安値を検出する。

    引数:
      df: OHLCデータのDataFrame
      swing_length: スイングを確定するためのローソク足の本数
                   (左右各swing_length本より高い/低い場合にスイング確定)

    戻り値:
      (swing_highs, swing_lows): SwingPointのリスト
    """
    swing_highs = []
    swing_lows = []

    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    for i in range(swing_length, n - swing_length):
        is_swing_high = all(
            highs[i] >= highs[i - j] and highs[i] >= highs[i + j]
            for j in range(1, swing_length + 1)
        )
        if is_swing_high:
            swing_highs.append(SwingPoint(
                index=i,
                price=highs[i],
                swing_type="high"
            ))

        is_swing_low = all(
            lows[i] <= lows[i - j] and lows[i] <= lows[i + j]
            for j in range(1, swing_length + 1)
        )
        if is_swing_low:
            swing_lows.append(SwingPoint(
                index=i,
                price=lows[i],
                swing_type="low"
            ))

    return swing_highs, swing_lows


# ============================================================
# 市場構造・BOS/CHOCHの検出
# ============================================================

def analyze_market_structure(
    df: pd.DataFrame,
    swing_highs: list,
    swing_lows: list
) -> MarketStructure:
    """
    スイング高値・安値から市場構造を判定し、BOS/CHOCHを検出する。
    """
    ms = MarketStructure()

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return ms

    recent_highs = sorted(swing_highs, key=lambda x: x.index)[-3:]
    recent_lows = sorted(swing_lows, key=lambda x: x.index)[-3:]

    if len(recent_highs) >= 2 and len(recent_lows) >= 2:
        last_high = recent_highs[-1].price
        prev_high = recent_highs[-2].price
        last_low = recent_lows[-1].price
        prev_low = recent_lows[-2].price

        ms.last_swing_high = last_high
        ms.last_swing_low = last_low

        # HH + HL → 上昇トレンド
        if last_high > prev_high and last_low > prev_low:
            ms.trend = "bullish"
        # LH + LL → 下降トレンド
        elif last_high < prev_high and last_low < prev_low:
            ms.trend = "bearish"
        else:
            ms.trend = "neutral"

    current_close = df["close"].iloc[-1]

    if ms.last_swing_high and ms.last_swing_low:
        if ms.trend == "bullish":
            if current_close > ms.last_swing_high:
                ms.bos_detected = True
                ms.bos_direction = "bullish"
            elif current_close < ms.last_swing_low:
                ms.choch_detected = True
                ms.choch_direction = "bearish"
        elif ms.trend == "bearish":
            if current_close < ms.last_swing_low:
                ms.bos_detected = True
                ms.bos_direction = "bearish"
            elif current_close > ms.last_swing_high:
                ms.choch_detected = True
                ms.choch_direction = "bullish"

    return ms


# ============================================================
# オーダーブロックの検出
# ============================================================

def detect_order_blocks(
    df: pd.DataFrame,
    swing_highs: list,
    swing_lows: list,
    lookback: int = 50
) -> list:
    """
    オーダーブロックを検出する。

    Bullish OB: 強い上昇の直前の陰線
    Bearish OB: 強い下降の直前の陽線
    """
    order_blocks = []
    closes = df["close"].values
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    start_idx = max(0, n - lookback)

    for i in range(start_idx + 2, n - 1):
        # Bullish OB
        if (closes[i] < opens[i] and
                closes[i + 1] > opens[i + 1] and
                closes[i + 1] > highs[i]):
            order_blocks.append(OrderBlock(
                ob_type="bullish",
                top=opens[i],
                bottom=closes[i],
                index=i,
            ))

        # Bearish OB
        elif (closes[i] > opens[i] and
              closes[i + 1] < opens[i + 1] and
              closes[i + 1] < lows[i]):
            order_blocks.append(OrderBlock(
                ob_type="bearish",
                top=closes[i],
                bottom=opens[i],
                index=i,
            ))

    current_price = closes[-1]
    for ob in order_blocks:
        ob.is_active = ob.bottom <= current_price <= ob.top

    return order_blocks[-10:]


# ============================================================
# 需給ゾーンの検出
# ============================================================

def detect_supply_demand_zones(
    df: pd.DataFrame,
    swing_highs: list,
    swing_lows: list
) -> list:
    """
    需給ゾーンを検出する。
    ATRの半分をゾーン幅として使用する。
    """
    zones = []
    current_price = df["close"].iloc[-1]
    atr = df["high"].sub(df["low"]).rolling(14).mean().iloc[-1]
    zone_width = atr * 0.5

    for sl in swing_lows[-5:]:
        zone = SupplyDemandZone(
            zone_type="demand",
            top=sl.price + zone_width,
            bottom=sl.price - zone_width,
            index=sl.index,
        )
        zone.is_active = zone.bottom <= current_price <= zone.top
        zones.append(zone)

    for sh in swing_highs[-5:]:
        zone = SupplyDemandZone(
            zone_type="supply",
            top=sh.price + zone_width,
            bottom=sh.price - zone_width,
            index=sh.index,
        )
        zone.is_active = zone.bottom <= current_price <= zone.top
        zones.append(zone)

    return zones


# ============================================================
# FVG(Fair Value Gap)の検出
# ============================================================

def detect_fair_value_gaps(
    df: pd.DataFrame, lookback: int = 30
) -> list:
    """
    FVG(Fair Value Gap)を検出する。

    Bullish FVG: 1本目の高値 < 3本目の安値
    Bearish FVG: 1本目の安値 > 3本目の高値
    """
    fvgs = []
    n = len(df)
    highs = df["high"].values
    lows = df["low"].values
    current_price = df["close"].iloc[-1]

    start_idx = max(0, n - lookback)

    for i in range(start_idx, n - 2):
        if highs[i] < lows[i + 2]:
            fvg = FairValueGap(
                fvg_type="bullish",
                top=lows[i + 2],
                bottom=highs[i],
                index=i + 1,
            )
            fvg.is_filled = current_price <= fvg.top
            fvgs.append(fvg)

        elif lows[i] > highs[i + 2]:
            fvg = FairValueGap(
                fvg_type="bearish",
                top=lows[i],
                bottom=highs[i + 2],
                index=i + 1,
            )
            fvg.is_filled = current_price >= fvg.bottom
            fvgs.append(fvg)

    return fvgs[-10:]


# ============================================================
# SMC分析のメイン関数
# ============================================================

def analyze_smc(
    df: pd.DataFrame, swing_length: int = 10
) -> SMCAnalysis:
    """
    SMC分析を実行してすべての結果を返す。

    引数:
      df: OHLCデータのDataFrame
      swing_length: スイングの期間(デフォルト10本)

    戻り値:
      SMCAnalysis: 全SMC情報
    """
    result = SMCAnalysis()

    if len(df) < swing_length * 2 + 5:
        return result

    swing_highs, swing_lows = detect_swing_points(df, swing_length)
    result.swing_highs = swing_highs
    result.swing_lows = swing_lows

    result.market_structure = analyze_market_structure(
        df, swing_highs, swing_lows
    )
    result.order_blocks = detect_order_blocks(df, swing_highs, swing_lows)
    result.supply_demand_zones = detect_supply_demand_zones(
        df, swing_highs, swing_lows
    )
    result.fair_value_gaps = detect_fair_value_gaps(df)

    return result
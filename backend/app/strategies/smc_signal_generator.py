"""
smc_signal_generator.py
========================

このファイルの役割:
  SMC分析の結果をもとに、100点満点のスコアを計算し、
  BUY/SELL/NO_TRADEを判定する。

スコア配分:
  市場構造(1時間足)  : 20点
  BOS/CHOCH(5分足)  : 25点
  Order Block       : 25点
  需給ゾーン         : 15点
  FVG               : 10点
  時間帯ボーナス      :  5点
  合計              : 100点
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd

from app.indicators.smc_analyzer import analyze_smc
from app.strategies.signal_generator import SignalResult, _score_to_label


# --- スコア配分 ---
SCORE_MARKET_STRUCTURE = 20
SCORE_BOS_CHOCH = 25
SCORE_ORDER_BLOCK = 25
SCORE_SUPPLY_DEMAND = 15
SCORE_FVG = 10
SCORE_SESSION = 5


def _get_session(timestamp: pd.Timestamp) -> str:
    """UTC時刻から取引セッションを判定する。"""
    hour_utc = timestamp.hour
    if 0 <= hour_utc < 7:
        return "asia"
    elif 7 <= hour_utc < 16:
        return "london"
    else:
        return "ny"


def generate_smc_signal(
    df_1h: pd.DataFrame,
    df_5m: pd.DataFrame,
    symbol: str = "XAUUSD",
) -> SignalResult:
    """
    SMCベースのシグナルを生成する。

    引数:
      df_1h  : 1時間足のOHLCデータ(市場構造判定用)
      df_5m  : 5分足のOHLCデータ(エントリー判定用)
      symbol : 銘柄名

    戻り値:
      SignalResult
    """
    reasons = {}
    score = 0.0

    if df_1h.empty or len(df_1h) < 25:
        return SignalResult(
            signal_type="NO_TRADE",
            score=0,
            strength_label="NONE",
            reasons={"error": "1時間足データ不足"},
        )
    if df_5m.empty or len(df_5m) < 25:
        return SignalResult(
            signal_type="NO_TRADE",
            score=0,
            strength_label="NONE",
            reasons={"error": "5分足データ不足"},
        )

    # SMC分析を実行
    smc_1h = analyze_smc(df_1h, swing_length=10)
    smc_5m = analyze_smc(df_5m, swing_length=10)

    latest_5m = df_5m.iloc[-1]
    current_price = float(latest_5m["close"])
    timestamp = latest_5m["timestamp"]

    session = _get_session(timestamp)
    is_active_session = session in ("london", "ny")

    ms_1h = smc_1h.market_structure
    ms_5m = smc_5m.market_structure

    if ms_1h.trend == "neutral":
        return SignalResult(
            signal_type="NO_TRADE",
            score=0,
            strength_label="NONE",
            reasons={"market_structure": "1時間足トレンドが中立のため見送り"},
        )

    is_buy_direction = ms_1h.trend == "bullish"

    # --- 1. 市場構造(1時間足) 20点 ---
    if ms_1h.trend == "bullish":
        score += SCORE_MARKET_STRUCTURE
        reasons["market_structure"] = "上昇構造(HH/HL)"
    elif ms_1h.trend == "bearish":
        score += SCORE_MARKET_STRUCTURE
        reasons["market_structure"] = "下降構造(LH/LL)"

    # --- 2. BOS/CHOCH(5分足) 25点 ---
    if is_buy_direction:
        if ms_5m.bos_detected and ms_5m.bos_direction == "bullish":
            score += SCORE_BOS_CHOCH
            reasons["bos_choch"] = "Bullish BOS確認"
        elif ms_5m.choch_detected and ms_5m.choch_direction == "bullish":
            score += SCORE_BOS_CHOCH
            reasons["bos_choch"] = "Bullish CHOCH(転換シグナル)"
        else:
            reasons["bos_choch"] = False
    else:
        if ms_5m.bos_detected and ms_5m.bos_direction == "bearish":
            score += SCORE_BOS_CHOCH
            reasons["bos_choch"] = "Bearish BOS確認"
        elif ms_5m.choch_detected and ms_5m.choch_direction == "bearish":
            score += SCORE_BOS_CHOCH
            reasons["bos_choch"] = "Bearish CHOCH(転換シグナル)"
        else:
            reasons["bos_choch"] = False

    # --- 3. Order Block 25点 ---
    active_obs = [ob for ob in smc_5m.order_blocks if ob.is_active]
    if is_buy_direction:
        bullish_obs = [ob for ob in active_obs if ob.ob_type == "bullish"]
        if bullish_obs:
            score += SCORE_ORDER_BLOCK
            reasons["order_block"] = f"Bullish OB接触({bullish_obs[-1].bottom:.2f}〜{bullish_obs[-1].top:.2f})"
        else:
            reasons["order_block"] = False
    else:
        bearish_obs = [ob for ob in active_obs if ob.ob_type == "bearish"]
        if bearish_obs:
            score += SCORE_ORDER_BLOCK
            reasons["order_block"] = f"Bearish OB接触({bearish_obs[-1].bottom:.2f}〜{bearish_obs[-1].top:.2f})"
        else:
            reasons["order_block"] = False

    # --- 4. 需給ゾーン(1時間足) 15点 ---
    active_zones = [z for z in smc_1h.supply_demand_zones if z.is_active]
    if is_buy_direction:
        demand_zones = [z for z in active_zones if z.zone_type == "demand"]
        if demand_zones:
            score += SCORE_SUPPLY_DEMAND
            reasons["supply_demand"] = f"Demandゾーン内({demand_zones[-1].bottom:.2f}〜{demand_zones[-1].top:.2f})"
        else:
            reasons["supply_demand"] = False
    else:
        supply_zones = [z for z in active_zones if z.zone_type == "supply"]
        if supply_zones:
            score += SCORE_SUPPLY_DEMAND
            reasons["supply_demand"] = f"Supplyゾーン内({supply_zones[-1].bottom:.2f}〜{supply_zones[-1].top:.2f})"
        else:
            reasons["supply_demand"] = False

    # --- 5. FVG(5分足) 10点 ---
    unfilled_fvgs = [f for f in smc_5m.fair_value_gaps if not f.is_filled]
    if is_buy_direction:
        bullish_fvgs = [f for f in unfilled_fvgs if f.fvg_type == "bullish"]
        if bullish_fvgs:
            score += SCORE_FVG
            reasons["fvg"] = "Bullish FVG存在"
        else:
            reasons["fvg"] = False
    else:
        bearish_fvgs = [f for f in unfilled_fvgs if f.fvg_type == "bearish"]
        if bearish_fvgs:
            score += SCORE_FVG
            reasons["fvg"] = "Bearish FVG存在"
        else:
            reasons["fvg"] = False

    # --- 6. 時間帯ボーナス 5点 ---
    if is_active_session:
        score += SCORE_SESSION
        reasons["session"] = f"{session.upper()}セッション(活発な時間帯)"
    else:
        reasons["session"] = "アジアセッション(静かな時間帯)"

    # --- ATR計算(SL/TP用) ---
    atr_value = None
    if "ATR_14" in df_5m.columns:
        atr_raw = df_5m["ATR_14"].iloc[-1]
        if pd.notna(atr_raw):
            atr_value = float(atr_raw)

    # --- SL/TP計算 ---
    stop_loss = None
    take_profit = None
    if atr_value is not None:
        if is_buy_direction:
            stop_loss = round(current_price - atr_value * 1.5, 2)
            take_profit = round(current_price + atr_value * 3.0, 2)
        else:
            stop_loss = round(current_price + atr_value * 1.5, 2)
            take_profit = round(current_price - atr_value * 3.0, 2)

    # --- 最終判定 ---
    strength_label = _score_to_label(score)
    if strength_label == "NONE":
        signal_type = "NO_TRADE"
    else:
        signal_type = "BUY" if is_buy_direction else "SELL"

    def _to_native(value):
        if hasattr(value, "item"):
            return value.item()
        return value

    reasons = {k: _to_native(v) for k, v in reasons.items()}

    return SignalResult(
        signal_type=signal_type,
        score=float(score),
        strength_label=strength_label,
        reasons=reasons,
        entry_price=current_price,
        atr_value=atr_value,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
"""
smc_signal_generator.py
========================

このファイルの役割:
  SMC分析の結果をもとに、100点満点のスコアを計算し、
  BUY/SELL/NO_TRADEを判定する。

スコア配分:
  市場構造(4時間足)  : 20点
  市場構造(1時間足)  : 15点
  BOS/CHOCH(15分足) : 20点
  Order Block(15分足): 15点
  需給ゾーン(1時間足) : 15点
  FVG(5分足)        : 10点
  1分足エントリー確認 :  5点
  合計              : 100点
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd

from app.indicators.smc_analyzer import analyze_smc


# --- SignalResultをここで定義(循環インポート回避) ---
@dataclass
class SignalResult:
    """シグナル判定の結果を表すデータ構造。"""
    signal_type: str
    score: float
    strength_label: str
    reasons: dict = field(default_factory=dict)
    entry_price: Optional[float] = None
    atr_value: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


def _score_to_label(score: float) -> str:
    """スコアを強度ラベルに変換する。"""
    if score >= 85:
        return "STRONG"
    if score >= 70:
        return "NORMAL"
    if score >= 60:
        return "WEAK"
    return "NONE"


# --- スコア配分 ---
SCORE_STRUCTURE_4H = 20
SCORE_STRUCTURE_1H = 15
SCORE_BOS_CHOCH = 20
SCORE_ORDER_BLOCK = 15
SCORE_SUPPLY_DEMAND = 15
SCORE_FVG = 10
SCORE_1M_ENTRY = 5


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
    df_4h: pd.DataFrame,
    df_1h: pd.DataFrame,
    df_15m: pd.DataFrame,
    df_5m: pd.DataFrame,
    symbol: str = "XAUUSD",
    df_1m: Optional[pd.DataFrame] = None,
) -> SignalResult:
    """
    SMCベースのシグナルを生成する(5時間足対応版)。
    """
    reasons = {}
    score = 0.0

    # データ不足チェック
    for tf, df in [("4時間足", df_4h), ("1時間足", df_1h),
                   ("15分足", df_15m), ("5分足", df_5m)]:
        if df is None or df.empty or len(df) < 25:
            return SignalResult(
                signal_type="NO_TRADE",
                score=0,
                strength_label="NONE",
                reasons={"error": f"{tf}データ不足"},
            )

    # SMC分析を実行
    smc_4h = analyze_smc(df_4h, swing_length=10)
    smc_1h = analyze_smc(df_1h, swing_length=10)
    smc_15m = analyze_smc(df_15m, swing_length=10)
    smc_5m = analyze_smc(df_5m, swing_length=10)

    latest_5m = df_5m.iloc[-1]
    current_price = float(latest_5m["close"])
    timestamp = latest_5m["timestamp"]
    session = _get_session(timestamp)

    ms_4h = smc_4h.market_structure
    ms_1h = smc_1h.market_structure
    ms_15m = smc_15m.market_structure

    # 4時間足のトレンドが不明な場合はNO_TRADE
    if ms_4h.trend == "neutral":
        return SignalResult(
            signal_type="NO_TRADE",
            score=0,
            strength_label="NONE",
            reasons={"market_structure_4h": "4時間足トレンドが中立のため見送り"},
        )

    is_buy_direction = ms_4h.trend == "bullish"

    # --- 1. 市場構造(4時間足) 20点 ---
    if ms_4h.trend == "bullish":
        score += SCORE_STRUCTURE_4H
        reasons["market_structure_4h"] = "上昇構造(HH/HL) [4H]"
    elif ms_4h.trend == "bearish":
        score += SCORE_STRUCTURE_4H
        reasons["market_structure_4h"] = "下降構造(LH/LL) [4H]"

    # --- 2. 市場構造(1時間足) 15点 ---
    if ms_1h.trend == ms_4h.trend:
        score += SCORE_STRUCTURE_1H
        reasons["market_structure_1h"] = f"1時間足トレンド一致({ms_1h.trend}) [1H]"
    else:
        reasons["market_structure_1h"] = False

    # --- 3. BOS/CHOCH(15分足) 20点 ---
    if is_buy_direction:
        if ms_15m.bos_detected and ms_15m.bos_direction == "bullish":
            score += SCORE_BOS_CHOCH
            reasons["bos_choch"] = "Bullish BOS確認 [15M]"
        elif ms_15m.choch_detected and ms_15m.choch_direction == "bullish":
            score += SCORE_BOS_CHOCH
            reasons["bos_choch"] = "Bullish CHOCH [15M]"
        else:
            reasons["bos_choch"] = False
    else:
        if ms_15m.bos_detected and ms_15m.bos_direction == "bearish":
            score += SCORE_BOS_CHOCH
            reasons["bos_choch"] = "Bearish BOS確認 [15M]"
        elif ms_15m.choch_detected and ms_15m.choch_direction == "bearish":
            score += SCORE_BOS_CHOCH
            reasons["bos_choch"] = "Bearish CHOCH [15M]"
        else:
            reasons["bos_choch"] = False

    # --- 4. Order Block(15分足) 15点 ---
    active_obs = [ob for ob in smc_15m.order_blocks if ob.is_active]
    if is_buy_direction:
        bullish_obs = [ob for ob in active_obs if ob.ob_type == "bullish"]
        if bullish_obs:
            score += SCORE_ORDER_BLOCK
            reasons["order_block"] = (
                f"Bullish OB接触 "
                f"({bullish_obs[-1].bottom:.2f}〜{bullish_obs[-1].top:.2f}) [15M]"
            )
        else:
            reasons["order_block"] = False
    else:
        bearish_obs = [ob for ob in active_obs if ob.ob_type == "bearish"]
        if bearish_obs:
            score += SCORE_ORDER_BLOCK
            reasons["order_block"] = (
                f"Bearish OB接触 "
                f"({bearish_obs[-1].bottom:.2f}〜{bearish_obs[-1].top:.2f}) [15M]"
            )
        else:
            reasons["order_block"] = False

    # --- 5. 需給ゾーン(1時間足) 15点 ---
    active_zones = [z for z in smc_1h.supply_demand_zones if z.is_active]
    if is_buy_direction:
        demand_zones = [z for z in active_zones if z.zone_type == "demand"]
        if demand_zones:
            score += SCORE_SUPPLY_DEMAND
            reasons["supply_demand"] = (
                f"Demandゾーン内 "
                f"({demand_zones[-1].bottom:.2f}〜{demand_zones[-1].top:.2f}) [1H]"
            )
        else:
            reasons["supply_demand"] = False
    else:
        supply_zones = [z for z in active_zones if z.zone_type == "supply"]
        if supply_zones:
            score += SCORE_SUPPLY_DEMAND
            reasons["supply_demand"] = (
                f"Supplyゾーン内 "
                f"({supply_zones[-1].bottom:.2f}〜{supply_zones[-1].top:.2f}) [1H]"
            )
        else:
            reasons["supply_demand"] = False

    # --- 6. FVG(5分足) 10点 ---
    unfilled_fvgs = [f for f in smc_5m.fair_value_gaps if not f.is_filled]
    if is_buy_direction:
        bullish_fvgs = [f for f in unfilled_fvgs if f.fvg_type == "bullish"]
        if bullish_fvgs:
            score += SCORE_FVG
            reasons["fvg"] = "Bullish FVG存在 [5M]"
        else:
            reasons["fvg"] = False
    else:
        bearish_fvgs = [f for f in unfilled_fvgs if f.fvg_type == "bearish"]
        if bearish_fvgs:
            score += SCORE_FVG
            reasons["fvg"] = "Bearish FVG存在 [5M]"
        else:
            reasons["fvg"] = False

    # --- 7. 1分足エントリー確認 5点 ---
    if df_1m is not None and not df_1m.empty and len(df_1m) >= 25:
        smc_1m = analyze_smc(df_1m, swing_length=5)
        ms_1m = smc_1m.market_structure
        entry_confirmed = False
        if is_buy_direction:
            if (ms_1m.bos_detected and ms_1m.bos_direction == "bullish") or \
               (ms_1m.choch_detected and ms_1m.choch_direction == "bullish"):
                entry_confirmed = True
        else:
            if (ms_1m.bos_detected and ms_1m.bos_direction == "bearish") or \
               (ms_1m.choch_detected and ms_1m.choch_direction == "bearish"):
                entry_confirmed = True

        if entry_confirmed:
            score += SCORE_1M_ENTRY
            reasons["entry_1m"] = "1分足エントリー確認 [1M]"
        else:
            reasons["entry_1m"] = False
    else:
        reasons["entry_1m"] = "1分足データなし"

    # セッション情報を記録
    reasons["session"] = f"{session.upper()}セッション"

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
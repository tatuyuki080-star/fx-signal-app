"""
signal_generator.py
====================

このファイルの役割:
  下位足(エントリー判定用の時間足)の指標データと、上位足トレンド方向を
  もとに、100点満点のスコアを計算し、BUY/SELL/NO_TRADEを判定する。
  さらに「なぜそのスコアになったか」という理由を構造化して返す
  (要件の「エントリー理由の可視化」に対応)。

スコア配分(合計100点):
  上位足一致   : 30点
  RSI         : 15点
  MACD        : 20点
  ATR         : 10点
  時間帯      : 10点
  ボリンジャー : 15点

スコア → 強度ラベル:
  85点以上 : STRONG
  70点以上 : NORMAL
  50点未満 : NONE (シグナルなし)
  50〜69点 : WEAK (シグナルは出すが強度は弱い扱い)

使い方(他のファイルから):
  from app.strategies.signal_generator import generate_signal
  result = generate_signal(df_entry_tf, trend_direction, symbol)
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd

from app.strategies.trend_analyzer import TrendDirection
from app.core.symbols_config import get_atr_threshold


SCORE_TREND_MATCH = 30
SCORE_RSI = 15
SCORE_MACD = 20
SCORE_ATR = 10
SCORE_TIME_OF_DAY = 10
SCORE_BOLLINGER = 15

THRESHOLD_STRONG = 85
THRESHOLD_NORMAL = 70
THRESHOLD_WEAK = 60


@dataclass
class SignalResult:
    """
    シグナル判定の結果を表すデータ構造。
    api/ や services/discord_notifier.py(今後実装)から参照しやすいよう、
    必要な情報をすべて1つにまとめている。
    """
    signal_type: str  # "BUY" / "SELL" / "NO_TRADE"
    score: float
    strength_label: str  # "STRONG" / "NORMAL" / "WEAK" / "NONE"
    reasons: dict = field(default_factory=dict)
    entry_price: Optional[float] = None
    atr_value: Optional[float] = None


def _is_london_or_ny_session(timestamp: pd.Timestamp) -> bool:
    """
    ロンドン時間・NY時間(取引が活発な時間帯)かどうかを判定する。

    簡易ルール(UTC基準):
      ロンドン時間: 8:00 - 17:00 UTC
      NY時間      : 13:00 - 22:00 UTC
      → 合わせて 8:00 - 22:00 UTC を「活発な時間帯」とみなす

    注意:
      これは簡易的な判定。サマータイムの影響で実際の時間帯は前後する。
      より厳密にするなら、経済指標カレンダーAPIとの連携が望ましいが、
      現段階ではシンプルな時間帯ルールで代替する。
    """
    hour_utc = timestamp.hour
    return 8 <= hour_utc < 22


def _check_rsi_reversal_buy(df: pd.DataFrame) -> bool:
    """
    RSIが35以下から反転(上昇)したかを判定する。
    """
    rsi_col = "RSI_14"
    if rsi_col not in df.columns or len(df) < 5:
        return False

    recent_rsi = df[rsi_col].tail(5)
    if recent_rsi.isna().any():
        return False

    latest_rsi = recent_rsi.iloc[-1]
    min_rsi_in_window = recent_rsi.iloc[:-1].min()

    return min_rsi_in_window <= 35 and latest_rsi > min_rsi_in_window


def _check_rsi_reversal_sell(df: pd.DataFrame) -> bool:
    """RSIが65以上から反転(下降)したかを判定する。"""
    rsi_col = "RSI_14"
    if rsi_col not in df.columns or len(df) < 5:
        return False

    recent_rsi = df[rsi_col].tail(5)
    if recent_rsi.isna().any():
        return False

    latest_rsi = recent_rsi.iloc[-1]
    max_rsi_in_window = recent_rsi.iloc[:-1].max()

    return max_rsi_in_window >= 65 and latest_rsi < max_rsi_in_window


def _check_macd_golden_cross(df: pd.DataFrame) -> bool:
    """
    MACDゴールデンクロス(MACD線がシグナル線を上抜け)を直近で検知したか判定する。
    """
    macd_col, signal_col = "MACD_12_26_9", "MACDs_12_26_9"
    if macd_col not in df.columns or len(df) < 2:
        return False

    prev = df.iloc[-2]
    latest = df.iloc[-1]

    if pd.isna(prev[macd_col]) or pd.isna(prev[signal_col]):
        return False
    if pd.isna(latest[macd_col]) or pd.isna(latest[signal_col]):
        return False

    was_below = prev[macd_col] <= prev[signal_col]
    now_above = latest[macd_col] > latest[signal_col]
    return was_below and now_above


def _check_macd_dead_cross(df: pd.DataFrame) -> bool:
    """MACDデッドクロス(MACD線がシグナル線を下抜け)を直近で検知したか判定する。"""
    macd_col, signal_col = "MACD_12_26_9", "MACDs_12_26_9"
    if macd_col not in df.columns or len(df) < 2:
        return False

    prev = df.iloc[-2]
    latest = df.iloc[-1]

    if pd.isna(prev[macd_col]) or pd.isna(prev[signal_col]):
        return False
    if pd.isna(latest[macd_col]) or pd.isna(latest[signal_col]):
        return False

    was_above = prev[macd_col] >= prev[signal_col]
    now_below = latest[macd_col] < latest[signal_col]
    return was_above and now_below


def _score_to_label(score: float) -> str:
    """スコアを強度ラベルに変換する。"""
    if score >= THRESHOLD_STRONG:
        return "STRONG"
    if score >= THRESHOLD_NORMAL:
        return "NORMAL"
    if score >= THRESHOLD_WEAK:
        return "WEAK"
    return "NONE"


def generate_signal(
    df_entry: pd.DataFrame,
    trend_direction: TrendDirection,
    symbol: str,
) -> SignalResult:
    """
    下位足の指標データと上位足トレンド方向から、シグナルを生成する。

    引数:
      df_entry       : indicators.add_all_indicators() 適用済みの
                        エントリー判定用時間足(例: 5分足)のDataFrame
      trend_direction: trend_analyzer.analyze_higher_timeframe_trend() の結果
      symbol         : "USDJPY" などアプリ内表記(ATR閾値の取得に使う)

    戻り値:
      SignalResult (signal_type, score, strength_label, reasonsを含む)
    """
    reasons: dict = {}

    if df_entry.empty or len(df_entry) < 5:
        return SignalResult(
            signal_type="NO_TRADE",
            score=0,
            strength_label="NONE",
            reasons={"data_insufficient": "価格データが不足しています"},
        )

    latest = df_entry.iloc[-1]

    if trend_direction == TrendDirection.NEUTRAL:
        return SignalResult(
            signal_type="NO_TRADE",
            score=0,
            strength_label="NONE",
            reasons={"higher_tf_trend": "上位足トレンドが不明瞭なため見送り"},
        )

    is_buy_direction = trend_direction == TrendDirection.UPTREND
    score = 0.0

    score += SCORE_TREND_MATCH
    reasons["higher_tf_trend"] = True

    if is_buy_direction:
        rsi_ok = _check_rsi_reversal_buy(df_entry)
    else:
        rsi_ok = _check_rsi_reversal_sell(df_entry)
    if rsi_ok:
        score += SCORE_RSI
    reasons["rsi_reversal"] = rsi_ok

    if is_buy_direction:
        macd_ok = _check_macd_golden_cross(df_entry)
    else:
        macd_ok = _check_macd_dead_cross(df_entry)
    if macd_ok:
        score += SCORE_MACD
    reasons["macd_cross"] = macd_ok

    sma50 = latest.get("SMA_50")
    if pd.notna(sma50):
        price_position_ok = (
            latest["close"] > sma50 if is_buy_direction else latest["close"] < sma50
        )
    else:
        price_position_ok = False
    reasons["price_vs_sma50"] = price_position_ok

    atr_value = latest.get("ATR_14")
    atr_threshold = get_atr_threshold(symbol)
    atr_ok = pd.notna(atr_value) and atr_value >= atr_threshold
    if atr_ok:
        score += SCORE_ATR
    reasons["atr_sufficient"] = atr_ok

    timestamp = latest.get("timestamp")
    time_ok = _is_london_or_ny_session(timestamp) if timestamp is not None else False
    if time_ok:
        score += SCORE_TIME_OF_DAY
    reasons["active_session"] = time_ok

    bbp = latest.get("BBP_20_2.0")
    if pd.notna(bbp):
        if is_buy_direction:
            bollinger_ok = bbp <= 0.3
        else:
            bollinger_ok = bbp >= 0.7
    else:
        bollinger_ok = False
    if bollinger_ok:
        score += SCORE_BOLLINGER
    reasons["bollinger_position"] = bollinger_ok

    # --- 最終判定 ---
    strength_label = _score_to_label(score)
    if strength_label == "NONE":
        signal_type = "NO_TRADE"
    else:
        signal_type = "BUY" if is_buy_direction else "SELL"

    # numpy.bool_ などのnumpyスカラー型が混ざっていると、FastAPIのJSON変換で
    # ValueError("'numpy.bool' object is not iterable") のようなエラーになる。
    # numpyのスカラー型は .item() でPython標準の型に変換できるので、
    # それを使って reasons の値をすべて安全な型に変換しておく。
    def _to_native_type(value):
        if hasattr(value, "item"):  # numpy.bool_, numpy.float64 など
            return value.item()
        return value

    reasons = {key: _to_native_type(value) for key, value in reasons.items()}

    return SignalResult(
        signal_type=signal_type,
        score=float(score),
        strength_label=strength_label,
        reasons=reasons,
        entry_price=float(latest.get("close")) if pd.notna(latest.get("close")) else None,
        atr_value=float(atr_value) if pd.notna(atr_value) else None,
    )
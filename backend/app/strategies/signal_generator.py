"""
signal_generator.py
====================

このファイルの役割:
  SignalResultデータクラスと_score_to_label関数を定義する。
  他のモジュールから参照される共通のデータ構造。
"""

from dataclasses import dataclass, field
from typing import Optional


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


def _to_native_type(value):
    """numpy型をPython標準型に変換する。"""
    if hasattr(value, "item"):
        return value.item()
    return value
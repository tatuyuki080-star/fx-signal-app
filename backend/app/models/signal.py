"""
signal.py
=========

このファイルの役割:
  シグナル判定の結果(BUY/SELL/NO_TRADE、スコア、エントリー理由など)を
  DBに保存するテーブル定義。

なぜ保存する?:
  - ダッシュボードに「過去のシグナル履歴」を表示するため
  - Discord通知の内容と同じ情報を後から見返せるようにするため
  - 将来バックテストや「シグナル精度の検証」をする際の元データになる

テーブル名: signals
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean
from sqlalchemy.sql import func

from app.core.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)

    # 通貨ペア。例: "USDJPY"
    symbol = Column(String(10), nullable=False, index=True)

    # 判定の基準にした時間足(エントリー判定側。例: "5min")
    timeframe = Column(String(10), nullable=False)

    # シグナルの種類: "BUY", "SELL", "NO_TRADE"
    signal_type = Column(String(10), nullable=False, index=True)

    # シグナル強度スコア(0〜100点)
    score = Column(Float, nullable=False)

    # スコアに応じた強度ラベル: "STRONG", "NORMAL", "NONE"
    # 85点以上=STRONG, 70点以上=NORMAL, 50点未満=NONE という運用を想定
    strength_label = Column(String(10), nullable=False)

    # 判定時点の価格情報
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)

    # ATR値(SL/TP計算の根拠として保存しておく)
    atr_value = Column(Float, nullable=True)

    # エントリー理由を構造化して保存(JSON形式)
    # 例: {"higher_tf_trend": true, "rsi_reversal": true, "macd_cross": true, ...}
    reasons = Column(JSON, nullable=True)

    # この相場が「エントリー禁止条件」に当たっていたかどうか
    is_blocked = Column(Boolean, default=False)

    # 禁止理由(あれば)。例: "経済指標30分前", "スプレッド拡大"
    blocked_reason = Column(String(255), nullable=True)

    # シグナルが生成された時刻
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<Signal {self.symbol} {self.signal_type} score={self.score}>"

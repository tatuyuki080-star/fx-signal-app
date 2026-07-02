"""
trade_log.py
============

このファイルの役割:
  シグナルをもとにユーザーが実際にエントリーした結果(勝敗・利益・損失)
  を記録するテーブル定義。

なぜ必要?:
  - 「このシグナルは本当に当たっていたのか」を後から検証できるようにする
  - 月別成績・勝率・PF(プロフィットファクター)などの集計の元データになる
  - バックテスト結果も同じ形式で保存することで、過去検証と実運用を
    同じロジックで集計できる

テーブル名: trade_logs

備考:
  このアプリは発注機能を持たないため、ここに記録される内容は
  「ユーザーが手動入力した結果」または「バックテストで自動計算した結果」
  のいずれかになる。
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func

from app.core.database import Base


class TradeLog(Base):
    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)

    # どのシグナルに基づくトレードか(紐付け用。手動入力の場合はNoneも許容)
    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True, index=True)

    symbol = Column(String(10), nullable=False, index=True)

    # "BUY" または "SELL"
    direction = Column(String(10), nullable=False)

    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)  # 決済前はNone

    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)

    # 勝敗: "WIN", "LOSE", "BREAKEVEN", まだ決済していなければNone
    result = Column(String(10), nullable=True)

    # 損益(pips、またはアカウント通貨での金額。運用方針に応じて使い分け)
    profit_loss_pips = Column(Float, nullable=True)

    # このログがバックテストによる生成かどうか
    is_backtest = Column(Boolean, default=False)

    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<TradeLog {self.symbol} {self.direction} result={self.result}>"

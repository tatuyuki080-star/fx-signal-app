"""
price_data.py
==============

このファイルの役割:
  Twelve Data APIから取得した価格データ(OHLCV)をDBに保存するための
  テーブル定義(SQLAlchemyモデル)。

なぜ価格データをDBに保存する?:
  - APIには無料枠のリクエスト数制限があるため、毎回APIを呼ぶのではなく
    一度取得したデータはDBに保存して再利用する
  - 過去データはバックテストでも使う
  - APIが一時的に落ちても、DBにあるデータで動作を継続できる

テーブル名: price_data
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint
from sqlalchemy.sql import func

from app.core.database import Base


class PriceData(Base):
    __tablename__ = "price_data"

    id = Column(Integer, primary_key=True, index=True)

    # 通貨ペア。例: "USDJPY", "EURUSD", "GBPJPY"
    symbol = Column(String(10), nullable=False, index=True)

    # 時間足。例: "1min", "5min", "15min", "1h", "4h"
    timeframe = Column(String(10), nullable=False, index=True)

    # このローソク足の開始時刻(UTC)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # OHLC(始値・高値・安値・終値)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)

    # 出来高(Twelve Dataのforexでは取得できない場合があるため、未取得時はNoneを許容)
    volume = Column(Float, nullable=True)

    # データを保存した時刻(デバッグ・監査用)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 同じ通貨・時間足・時刻のデータが重複して入らないようにする制約
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_price_data_symbol_tf_ts"),
    )

    def __repr__(self):
        return f"<PriceData {self.symbol} {self.timeframe} {self.timestamp} close={self.close}>"

"""
price_data_service.py
======================

このファイルの役割:
  twelve_data_client.py で取得したOHLCVデータ(pandas DataFrame)を、
  price_data テーブルに保存する。
"""

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.price_data import PriceData


def save_price_data(db: Session, symbol: str, timeframe: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    incoming_timestamps = df["timestamp"].tolist()

    existing_rows = db.execute(
        select(PriceData.timestamp).where(
            PriceData.symbol == symbol,
            PriceData.timeframe == timeframe,
            PriceData.timestamp.in_(incoming_timestamps),
        )
    ).scalars().all()
    existing_timestamps = set(existing_rows)

    saved_count = 0
    for _, row in df.iterrows():
        if row["timestamp"] in existing_timestamps:
            continue

        price_record = PriceData(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=row["timestamp"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"] if pd.notna(row["volume"]) else None,
        )
        db.add(price_record)
        saved_count += 1

    db.commit()
    return saved_count


def get_recent_price_data(
    db: Session, symbol: str, timeframe: str, limit: int = 200
) -> pd.DataFrame:
    rows = db.execute(
        select(PriceData)
        .where(PriceData.symbol == symbol, PriceData.timeframe == timeframe)
        .order_by(PriceData.timestamp.desc())
        .limit(limit)
    ).scalars().all()

    if not rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    data = [
        {
            "timestamp": r.timestamp,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume,
        }
        for r in rows
    ]
    df = pd.DataFrame(data)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df
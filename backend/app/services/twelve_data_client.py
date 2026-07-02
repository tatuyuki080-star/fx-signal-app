"""
twelve_data_client.py
======================

このファイルの役割:
  Twelve Data API にHTTPリクエストを送り、OHLCV(始値・高値・安値・終値・出来高)
  データを取得する「窓口」。

なぜ分離する?:
  この後 indicators/ や strategies/ では「データをどこから取得したか」を
  意識せず、すでに整形されたデータ(pandas DataFrame)を使えるようにしたい。
  もし将来 Twelve Data から別のAPIに切り替える場合も、
  このファイルの中身を直すだけで他のコードに影響しないようにする。

使い方(他のファイルから):
  from app.services.twelve_data_client import fetch_time_series
  df = await fetch_time_series("USD/JPY", "5min")
"""

import asyncio
import httpx
import pandas as pd

from app.core.config import settings

# Twelve Data APIのベースURL
BASE_URL = "https://api.twelvedata.com/time_series"

# アプリ内で使う時間足の表記 → Twelve Data API が要求する interval 表記の対応表
# (アプリ内では "5m" のような短い表記を使い、API呼び出し時だけ変換する)
TIMEFRAME_MAP = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
}

# 429 (Too Many Requests) が出た場合に何秒待ってリトライするか
RATE_LIMIT_RETRY_WAIT_SECONDS = 15
# 429リトライの最大回数(これを超えたら諦めてエラーにする)
MAX_RATE_LIMIT_RETRIES = 2


class TwelveDataError(Exception):
    """Twelve Data APIからのエラー応答、または通信失敗を表す例外。"""
    pass


async def fetch_time_series(
    symbol: str,
    timeframe: str,
    output_size: int = 100,
) -> pd.DataFrame:
    """
    指定した通貨ペア・時間足のOHLCVデータを取得し、pandas DataFrameで返す。

    引数:
      symbol     : 通貨ペア。例: "USD/JPY", "EUR/USD", "XAU/USD"
                   ※ Twelve Dataの表記は "USD/JPY" のようにスラッシュを使う点に注意。
                     アプリ内の保存名("USDJPY")とは表記が違うので、
                     呼び出し側で変換が必要(後述のSYMBOL_MAPを参照)。
      timeframe  : アプリ内表記。例: "5m", "1h"
      output_size: 取得するローソク足の本数(最大5000程度。デフォルトは100本)

    戻り値:
      pandas.DataFrame で、以下のカラムを持つ:
        timestamp, open, high, low, close, volume
      新しい順(降順)でAPIから返ってくるが、ここで古い順(昇順)に並び替えて返す。
      (指標計算は古い→新しいの順で行うのが自然なため)

    レート制限対策:
      Twelve Dataの無料プランは1分あたり8リクエストの制限がある。
      429 (Too Many Requests) が返った場合、RATE_LIMIT_RETRY_WAIT_SECONDS秒待って
      最大MAX_RATE_LIMIT_RETRIES回までリトライする。

    例外:
      TwelveDataError: APIがエラーを返した場合、通信に失敗した場合、
                       リトライしても429が解消しなかった場合
    """
    if timeframe not in TIMEFRAME_MAP:
        raise ValueError(f"未対応の時間足です: {timeframe}")

    interval = TIMEFRAME_MAP[timeframe]

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": output_size,
        "apikey": settings.TWELVE_DATA_API_KEY,
    }

    response = None
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(BASE_URL, params=params)
                if response.status_code == 429:
                    if attempt < MAX_RATE_LIMIT_RETRIES:
                        # レート制限に達した場合、少し待ってからリトライする
                        await asyncio.sleep(RATE_LIMIT_RETRY_WAIT_SECONDS)
                        continue
                    else:
                        raise TwelveDataError(
                            f"Twelve Data APIのレート制限(429)が解消しませんでした"
                            f"({MAX_RATE_LIMIT_RETRIES}回リトライ後も失敗): {symbol} {timeframe}"
                        )
                response.raise_for_status()
                break  # 成功したらリトライループを抜ける
            except httpx.HTTPError as e:
                if response is not None and response.status_code == 429:
                    continue
                # str(e) が空になるケース(タイムアウト等)もあるため、型名も含めて記録する
                error_detail = str(e) or repr(e)
                raise TwelveDataError(
                    f"Twelve Data APIへの通信に失敗しました "
                    f"({type(e).__name__}): {error_detail}"
                ) from e

    data = response.json()

    # Twelve Dataはエラー時も200 OKで {"status": "error", "message": "..."} を返すことがある
    if data.get("status") == "error":
        raise TwelveDataError(f"Twelve Data APIがエラーを返しました: {data.get('message')}")

    values = data.get("values")
    if not values:
        raise TwelveDataError(f"{symbol} {timeframe} のデータが空でした")

    df = pd.DataFrame(values)

    # APIのレスポンスはすべて文字列型なので、数値型に変換する
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize("UTC")
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)

    # volumeはforexでは提供されない場合があるため、無ければ追加してNoneにする
    if "volume" in df.columns:
        df["volume"] = df["volume"].astype(float)
    else:
        df["volume"] = None

    df = df.rename(columns={"datetime": "timestamp"})
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]

    # APIは新しい順で返すので、古い順に並び替える
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df
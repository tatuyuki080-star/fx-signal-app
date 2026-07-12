"""
technical_indicators.py
========================

このファイルの役割:
  価格データ(OHLC)から、テクニカル指標を計算する純粋な関数群。

設計方針:
  - このファイルはDBアクセスやAPI呼び出しを一切行わない。
    「DataFrameを受け取り、指標列を追加したDataFrameを返す」だけにする。
    → テストが書きやすく、後で指標を追加・修正しやすくなるため。
  - 内部では pandas_ta_classic を使う。
    (元の pandas_ta は配布が止まっているため、コミュニティ版を採用している。
     経緯は requirements.txt のコメントを参照)

使い方(他のファイルから):
  from app.indicators.technical_indicators import add_all_indicators
  df_with_indicators = add_all_indicators(df)
"""

import pandas as pd
import pandas_ta_classic as ta


def add_sma(df: pd.DataFrame, period: int, column: str = "close") -> pd.DataFrame:
    """
    単純移動平均線(SMA)を追加する。

    例: add_sma(df, 20) → "SMA_20" 列が追加される
    """
    df[f"SMA_{period}"] = ta.sma(df[column], length=period)
    return df


def add_ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.DataFrame:
    """
    指数移動平均線(EMA)を追加する。

    例: add_ema(df, 20) → "EMA_20" 列が追加される
    """
    df[f"EMA_{period}"] = ta.ema(df[column], length=period)
    return df


def add_rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.DataFrame:
    """
    RSI(相対力指数)を追加する。

    RSIとは:
      0〜100の範囲で「買われすぎ/売られすぎ」を判定する指標。
      一般に70以上で買われすぎ、30以下で売られすぎとされる。
      このアプリでは「35以下から反転」「65以上から反転」を
      BUY/SELL条件に使う(strategies/ で実装)。

    例: add_rsi(df) → "RSI_14" 列が追加される
    """
    df[f"RSI_{period}"] = ta.rsi(df[column], length=period)
    return df


def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close",
) -> pd.DataFrame:
    """
    MACD(移動平均収束拡散法)を追加する。

    MACDとは:
      短期EMAと長期EMAの差(MACD線)と、その移動平均(シグナル線)を見て、
      トレンドの勢いや転換点を判定する指標。
      MACD線がシグナル線を上に抜けることを「ゴールデンクロス」、
      下に抜けることを「デッドクロス」と呼ぶ。

    追加される列:
      MACD_{fast}_{slow}_{signal}     : MACD線
      MACDh_{fast}_{slow}_{signal}    : ヒストグラム(MACD線とシグナル線の差)
      MACDs_{fast}_{slow}_{signal}    : シグナル線
    """
    macd_result = ta.macd(df[column], fast=fast, slow=slow, signal=signal)
    df = pd.concat([df, macd_result], axis=1)
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    ATR(Average True Range、平均真の値幅)を追加する。

    ATRとは:
      直近の価格変動の大きさ(ボラティリティ)を表す指標。
      このアプリでは、
        - エントリー禁止条件「ATRが低すぎる」の判定
        - SL = ATR × 1.5 のリスク管理計算
      の両方に使う重要な指標。

    例: add_atr(df) → "ATR_14" 列が追加される

    注意:
      ATR計算には high, low, close の3列が必要。
    """
    df[f"ATR_{period}"] = ta.atr(df["high"], df["low"], df["close"], length=period)
    return df


def add_bollinger_bands(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, column: str = "close"
) -> pd.DataFrame:
    """
    ボリンジャーバンドを追加する。

    ボリンジャーバンドとは:
      移動平均線を中心に、価格の標準偏差の幅でバンド(上限・下限)を引いた指標。
      価格がバンドの外に出ると「買われすぎ/売られすぎ」の目安になる。

    追加される列:
      BBL_{period}_{std_dev} : 下限バンド
      BBM_{period}_{std_dev} : 中央線(移動平均線)
      BBU_{period}_{std_dev} : 上限バンド
      BBB_{period}_{std_dev} : バンド幅
      BBP_{period}_{std_dev} : 現在価格のバンド内位置(0〜1)
    """
    bbands_result = ta.bbands(df[column], length=period, std=std_dev)
    df = pd.concat([df, bbands_result], axis=1)
    return df

def add_stochastic(
    df: pd.DataFrame, k_period: int = 5, d_period: int = 3
) -> pd.DataFrame:
    """
    ストキャスティクス(%K, %D)を追加する。
    5分足用に k_period=5 に設定している。
    """
    stoch_result = ta.stoch(df["high"], df["low"], df["close"], k=k_period, d=d_period)
    df = pd.concat([df, stoch_result], axis=1)
    return df


def add_ema_cross(df: pd.DataFrame) -> pd.DataFrame:
    """
    EMA5とEMA13を追加する(5分足用短期EMAクロス)。
    """
    df["EMA_5"] = ta.ema(df["close"], length=5)
    df["EMA_13"] = ta.ema(df["close"], length=13)
    return df


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    要件で定義されたすべての指標を一括で追加する。
    """
    df = df.copy()

    df = add_sma(df, 20)
    df = add_sma(df, 50)
    df = add_sma(df, 200)
    df = add_ema(df, 20)
    df = add_ema_cross(df)
    df = add_rsi(df, 9)
    df = add_macd(df)
    df = add_atr(df, 14)
    df = add_bollinger_bands(df, 20, 2.0)
    df = add_stochastic(df, 5, 3)

    return df
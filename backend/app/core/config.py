"""
config.py
=========

このファイルの役割:
  .env に書いた環境変数を、Pythonのコードから型安全に読み込むための
  「設定クラス」を定義する。

なぜ必要?:
  os.environ["TWELVE_DATA_API_KEY"] のように直接書くと、
  - 変数名のタイプミスに気づきにくい
  - 値が無い場合のエラーが分かりにくい
  - 型(文字列・数値など)が保証されない
  という問題がある。pydantic-settings を使うと、
  これらをまとめて解決できる。

使い方(他のファイルから):
  from app.core.config import settings
  print(settings.TWELVE_DATA_API_KEY)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- データベース ---
    DATABASE_URL: str

    # --- Twelve Data API ---
    TWELVE_DATA_API_KEY: str

    # --- Discord Webhook ---
    DISCORD_WEBHOOK_URL: str

    # --- OpenAI API ---
    OPENAI_API_KEY: str = ""

    # --- 認証 ---
    SECRET_KEY: str

    # --- アプリ動作設定 ---
    ENVIRONMENT: str = "development"
    POLLING_INTERVAL_SECONDS: int = 300

    # .env ファイルから読み込む設定
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .envに余分な変数があってもエラーにしない
    )


# このインスタンスをアプリ全体で共有して使う
# (毎回 Settings() を作り直すと、その都度.envを再読み込みしてしまうため)
settings = Settings()

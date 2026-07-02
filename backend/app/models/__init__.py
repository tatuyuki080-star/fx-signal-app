"""
models/__init__.py
===================

このファイルの役割:
  models/ 配下の各テーブル定義をまとめてインポートする。

なぜ必要?:
  Alembic(DBマイグレーションツール)は、Base.metadata に登録された
  モデルを見てテーブルを作成する。各モデルファイルを「どこかで」
  インポートしないと、Pythonがそのファイルを読み込まず、
  Base.metadata にテーブル情報が登録されない。
  ここでまとめてインポートすることで、
  「from app.models import *」的に一括で認識できるようにする。
"""

from app.models.price_data import PriceData  # noqa: F401
from app.models.signal import Signal  # noqa: F401
from app.models.trade_log import TradeLog  # noqa: F401

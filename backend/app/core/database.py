"""
database.py
============

このファイルの役割:
  PostgreSQLへの接続を管理する。SQLAlchemyという「ORM」を使うことで、
  SQL文を直接書かなくても、Pythonのクラスとしてテーブルを操作できる。

主な3つの部品:
  1. engine   : DBへの実際の接続経路
  2. SessionLocal : 1回のリクエストごとに使う「作業単位」
  3. Base     : すべてのテーブルモデル(models/ 配下)が継承する土台クラス

使い方(他のファイルから):
  from app.core.database import get_db
  → FastAPIのエンドポイントで Depends(get_db) として使う
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# --- DBへの接続経路を作成 ---
# pool_pre_ping=True: 接続が切れていた場合に自動で再接続を試みる
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# --- セッション(DB操作の単位)を作るための工場 ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- すべてのテーブルモデルの土台となるクラス ---
Base = declarative_base()


def get_db():
    """
    FastAPIのエンドポイントでDBセッションを使うための関数。

    なぜ yield を使う?:
      リクエスト処理が終わった後(成功・失敗どちらでも)、
      必ずセッションを閉じる(db.close())必要があるため。
      try/finally を使うことで「処理が終わったら必ず後始末する」を保証する。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

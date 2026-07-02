"""
alembic/env.py
===============

このファイルの役割:
  Alembicがマイグレーションを実行する際の「設定」を行う場所。
  自動生成された内容に、以下2点を追加している。

  1. target_metadata に models/ の Base.metadata を渡す
     → これにより `alembic revision --autogenerate` を実行したとき、
       「models/ で定義したテーブルと、実際のDBの差分」を
       Alembicが自動で検出できるようになる。

  2. DB接続URLを .env の DATABASE_URL から取得する
     → alembic.ini に直接パスワードなどを書きたくないため。
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# --- ここから追加した部分 ---
import sys
import os

# backend/ ディレクトリをパスに追加(app/ をインポートできるようにするため)
sys.path.append(os.getcwd())

from app.core.config import settings
from app.core.database import Base
from app import models  # noqa: F401  (これを書くことで全モデルがBaseに登録される)

target_metadata = Base.metadata
# --- 追加した部分はここまで ---

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# .env の DATABASE_URL を alembic.ini の設定より優先して使う
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
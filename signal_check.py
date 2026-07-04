"""
signal_check.py
================

このファイルの役割:
  GitHub Actionsから5分おきに実行される、シグナルチェックの単体スクリプト。
  Supabase(クラウドPostgreSQL)に接続し、価格データ取得→指標計算→
  シグナル判定→Discord通知を行う。

  Macを起動していなくてもDiscord通知が届くようにするのがこのスクリプトの目的。
  バックエンドのscheduler.pyと同じロジックを使っているが、
  FastAPIやAPSchedulerなどの依存関係が不要なシンプルな形にしている。
"""

import asyncio
import logging
import os
import sys

# backendのapp/ディレクトリをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """全銘柄のシグナルチェックを実行する。"""
    from app.services.scheduler import check_signal_for_symbol_with_result, API_REQUEST_INTERVAL_SECONDS
    from app.core.symbols_config import SYMBOLS

    logger.info("=== シグナルチェック開始 ===")

    symbol_list = list(SYMBOLS.keys())
    for i, symbol in enumerate(symbol_list):
        result = await check_signal_for_symbol_with_result(symbol)
        logger.info(f"{symbol}: {result}")
        if i < len(symbol_list) - 1:
            await asyncio.sleep(API_REQUEST_INTERVAL_SECONDS)

    logger.info("=== シグナルチェック完了 ===")


if __name__ == "__main__":
    asyncio.run(main())
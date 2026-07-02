"""
discord_notifier.py
====================

このファイルの役割:
  シグナル判定結果(SignalResult)を、Discord Webhookを使って
  指定チャンネルに通知する。

設計方針:
  - 「通知を送る」という処理だけに専念させる。
    シグナルをいつ・どの条件で送るか(strength_labelがWEAK以上のときだけ、等)
    は呼び出し側(ポーリング処理やAPIエンドポイント)が決める。
  - 後でWeb Push通知などを追加する場合も、同じ形の関数を
    web_push_notifier.py のような別ファイルに用意し、
    呼び出し側で両方呼ぶだけで済むようにする。

使い方(他のファイルから):
  from app.services.discord_notifier import send_signal_notification
  await send_signal_notification(symbol="USDJPY", result=signal_result)
"""

import httpx

from app.core.config import settings
from app.strategies.signal_generator import SignalResult


# シグナルの理由キー → 日本語の表示文言の対応表
# (Discord通知やフロントエンドで人間が読みやすい形にするため)
REASON_LABELS = {
    "higher_tf_trend": "上位足トレンド一致",
    "rsi_reversal": "RSI反転",
    "macd_cross": "MACDクロス",
    "price_vs_sma50": "価格がSMA50に対して優位",
    "atr_sufficient": "ATR十分(ボラティリティ良好)",
    "active_session": "活発な時間帯(ロンドン/NY)",
    "bollinger_position": "ボリンジャーバンド良好",
}


def _build_reasons_text(reasons: dict) -> str:
    """
    reasons辞書(項目名→True/False)を、Discordメッセージ用の
    箇条書きテキストに変換する。

    True の項目だけを「理由」として表示する
    (False の項目を並べても情報として有用ではないため)。
    """
    lines = []
    for key, value in reasons.items():
        if value is True:
            label = REASON_LABELS.get(key, key)
            lines.append(f"- {label}")

    if not lines:
        return "- (該当条件なし)"

    return "\n".join(lines)


def _build_embed(symbol: str, result: SignalResult) -> dict:
    """
    Discordの「embed」(カード形式の装飾メッセージ)を組み立てる。

    embedを使う理由:
      プレーンテキストよりも見やすく、色分け(BUYは緑、SELLは赤など)で
      直感的に種類が分かるようにするため。
    """
    color_map = {
        "BUY": 0x2ECC71,   # 緑
        "SELL": 0xE74C3C,  # 赤
        "NO_TRADE": 0x95A5A6,  # グレー
    }
    color = color_map.get(result.signal_type, 0x95A5A6)

    fields = [
        {"name": "シグナルスコア", "value": f"{result.score:.0f} / 100点 ({result.strength_label})", "inline": True},
    ]

    if result.entry_price is not None:
        fields.append({"name": "エントリー価格目安", "value": f"{result.entry_price:.5f}", "inline": True})

    if result.atr_value is not None:
        fields.append({"name": "ATR", "value": f"{result.atr_value:.5f}", "inline": True})

    fields.append({"name": "エントリー理由", "value": _build_reasons_text(result.reasons), "inline": False})

    return {
        "title": f"{symbol} {result.signal_type}",
        "color": color,
        "fields": fields,
    }


async def send_signal_notification(symbol: str, result: SignalResult) -> bool:
    """
    シグナル判定結果をDiscordに通知する。

    引数:
      symbol: アプリ内表記。例: "USDJPY"
      result: strategies/signal_generator.py の generate_signal() が返す結果

    戻り値:
      送信に成功したら True、失敗したら False
      (通知の失敗でアプリ全体を止めたくないため、例外は投げずbool で返す)
    """
    payload = {
        "embeds": [_build_embed(symbol, result)],
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.DISCORD_WEBHOOK_URL, json=payload)
            response.raise_for_status()
        return True
    except httpx.HTTPError:
        return False
"""
ai_analyzer.py
===============

このファイルの役割:
  OpenAI GPT-4o miniを使って、シグナル判定結果を
  人間が読みやすい日本語で説明する。

  AIはシグナルの「予測」ではなく「説明・補助」を担当する。
  実際のシグナル判定はバックエンドのルールベースで行い、
  AIはその結果を解釈して説明文を生成するだけ。
"""

import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


async def analyze_signal_with_ai(
    symbol: str,
    signal_type: str,
    score: float,
    strength_label: str,
    higher_tf_trend: str,
    reasons: dict,
    entry_price: float | None,
    stop_loss: float | None,
    take_profit: float | None,
    atr_value: float | None,
) -> dict:
    """
    シグナル判定結果をOpenAI GPT-4o miniに送り、
    日本語の分析コメントを生成する。

    戻り値:
      {
        "summary": "相場状況の要約",
        "confidence": "高/中/低",
        "advice": "エントリーアドバイス",
        "risk_warning": "リスク警告"
      }

    エラー時はデフォルトの辞書を返す(AI失敗でアプリ全体を止めない)。
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("OPENAI_API_KEYが設定されていません。AI分析をスキップします。")
        return _default_response()

    # reasonsの日本語変換
    reason_labels = {
        "higher_tf_trend": "上位足トレンド一致",
        "rsi_reversal": "RSI反転",
        "macd_cross": "MACDクロス",
        "ema_cross": "EMAクロス",
        "stochastic_reversal": "ストキャスティクス反転",
        "price_vs_sma50": "価格がSMA50に対して優位",
        "atr_sufficient": "ATR十分",
        "active_session": "活発な時間帯",
        "bollinger_position": "ボリンジャーバンド良好",
    }

    active_reasons = [
        reason_labels.get(k, k)
        for k, v in reasons.items()
        if v is True
    ]

    trend_labels = {
        "UPTREND": "上昇トレンド",
        "DOWNTREND": "下降トレンド",
        "NEUTRAL": "中立",
    }

    prompt_data = {
        "銘柄": symbol,
        "シグナル": signal_type,
        "スコア": f"{score}/100点",
        "強度": strength_label,
        "上位足トレンド": trend_labels.get(higher_tf_trend, higher_tf_trend),
        "エントリー条件": active_reasons if active_reasons else ["条件なし"],
        "エントリー価格": entry_price,
        "損切りライン": stop_loss,
        "利確ポイント": take_profit,
        "ATR": atr_value,
    }

    system_prompt = """あなたはFXトレードのテクニカル分析アシスタントです。
与えられたシグナルデータを分析し、以下のJSON形式で回答してください。

{
  "summary": "相場状況の簡潔な説明(2〜3文)",
  "confidence": "高/中/低のいずれか",
  "advice": "エントリーに関するアドバイス(1〜2文)",
  "risk_warning": "注意すべきリスク(1文、なければnull)"
}

重要: これは投資助言ではなく、テクニカル分析の説明です。
JSONのみを返してください。余分なテキストは不要です。"""

    user_prompt = f"以下のシグナルデータを分析してください:\n{json.dumps(prompt_data, ensure_ascii=False, indent=2)}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                OPENAI_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            return result

    except Exception as e:
        logger.error(f"AI分析エラー: {e}")
        return _default_response()


def _default_response() -> dict:
    """AI分析が失敗した場合のデフォルト値。"""
    return {
        "summary": "AI分析を取得できませんでした。",
        "confidence": "不明",
        "advice": "テクニカル指標を参考にご判断ください。",
        "risk_warning": None,
    }
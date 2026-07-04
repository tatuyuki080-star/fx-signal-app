/**
 * SignalPanel.tsx
 * ================
 *
 * このファイルの役割:
 *   現在のシグナル(BUY/SELL/NO_TRADE)・スコア・トレンド方向・
 *   エントリー理由を表示するパネル。
 *
 * 要件との対応:
 *   「エントリー理由の可視化」を実現する中心的なコンポーネント。
 */

"use client";

import { SignalData } from "@/types/signal";

interface SignalPanelProps {
  data: SignalData | null;
  isLoading: boolean;
  error: string | null;
}

const REASON_LABELS: Record<string, string> = {
  higher_tf_trend: "上位足トレンド一致",
  rsi_reversal: "RSI反転",
  macd_cross: "MACDクロス",
  price_vs_sma50: "価格がSMA50に対して優位",
  atr_sufficient: "ATR十分(ボラティリティ良好)",
  active_session: "活発な時間帯(ロンドン/NY)",
  bollinger_position: "ボリンジャーバンド良好",
};

const TREND_LABELS: Record<string, string> = {
  UPTREND: "上昇トレンド",
  DOWNTREND: "下降トレンド",
  NEUTRAL: "中立(様子見)",
};

function getSignalTypeStyle(signalType: string) {
  switch (signalType) {
    case "BUY":
      return {
        bg: "bg-[var(--color-buy-bg)]",
        text: "text-[var(--color-buy)]",
        label: "BUY",
      };
    case "SELL":
      return {
        bg: "bg-[var(--color-sell-bg)]",
        text: "text-[var(--color-sell)]",
        label: "SELL",
      };
    default:
      return {
        bg: "bg-[var(--color-neutral-bg)]",
        text: "text-[var(--color-neutral)]",
        label: "NO TRADE",
      };
  }
}

function getStrengthColor(label: string) {
  switch (label) {
    case "STRONG":
      return "text-[var(--color-strong)]";
    case "NORMAL":
      return "text-[var(--color-normal)]";
    case "WEAK":
      return "text-[var(--color-weak)]";
    default:
      return "text-[var(--foreground-muted)]";
  }
}

export default function SignalPanel({ data, isLoading, error }: SignalPanelProps) {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-[var(--border-color)] bg-[var(--background-panel)] p-6">
        <p className="text-[var(--foreground-muted)] text-sm">読み込み中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-[var(--border-color)] bg-[var(--background-panel)] p-6">
        <p className="text-[var(--color-sell)] text-sm">{error}</p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const signalStyle = getSignalTypeStyle(data.signal_type);

  const activeReasons = Object.entries(data.reasons)
    .filter(([, value]) => value === true)
    .map(([key]) => REASON_LABELS[key] || key);

  return (
    <div className="rounded-xl border border-[var(--border-color)] bg-[var(--background-panel)] p-6 space-y-5">
      <div className={`rounded-lg ${signalStyle.bg} p-4 text-center`}>
        <span className={`text-3xl font-bold ${signalStyle.text}`}>
          {signalStyle.label}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-[var(--foreground-muted)] mb-1">
            シグナルスコア
          </p>
          <p className="text-xl font-semibold">{data.score} / 100</p>
        </div>
        <div>
          <p className="text-xs text-[var(--foreground-muted)] mb-1">強度</p>
          <p className={`text-xl font-semibold ${getStrengthColor(data.strength_label)}`}>
            {data.strength_label}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-xs text-[var(--foreground-muted)] mb-1">
            上位足トレンド
          </p>
          <p>{TREND_LABELS[data.higher_tf_trend] || data.higher_tf_trend}</p>
        </div>
        {data.entry_price !== null && (
          <div>
            <p className="text-xs text-[var(--foreground-muted)] mb-1">
              エントリー価格目安
            </p>
            <p>{data.entry_price.toFixed(5)}</p>
          </div>
        )}
        {data.atr_value !== null && (
          <div>
            <p className="text-xs text-[var(--foreground-muted)] mb-1">ATR</p>
            <p>{data.atr_value.toFixed(5)}</p>
          </div>
        )}
      </div>

      <div>
        <p className="text-xs text-[var(--foreground-muted)] mb-2">
          エントリー理由
        </p>
        {activeReasons.length > 0 ? (
          <ul className="space-y-1">
            {activeReasons.map((reason) => (
              <li key={reason} className="flex items-center gap-2 text-sm">
                <span className="text-[var(--color-buy)]">●</span>
                {reason}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-[var(--foreground-muted)]">
            該当する条件がありません
          </p>
        )}
      </div>
    </div>
  );
}
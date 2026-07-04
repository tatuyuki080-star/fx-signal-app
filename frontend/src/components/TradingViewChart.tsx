/**
 * TradingViewChart.tsx
 * ======================
 *
 * このファイルの役割:
 *   TradingViewの無料ウィジェットを埋め込み、ローソク足チャートを表示する。
 */

"use client";

import { useEffect, useRef } from "react";

interface TradingViewChartProps {
  symbol: string;
}

const TRADINGVIEW_SYMBOL_MAP: Record<string, string> = {
  USDJPY: "OANDA:USDJPY",
  EURUSD: "OANDA:EURUSD",
  GBPJPY: "OANDA:GBPJPY",
  XAUUSD: "TVC:GOLD",
};

export default function TradingViewChart({ symbol }: TradingViewChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    containerRef.current.innerHTML = "";

    const tvSymbol = TRADINGVIEW_SYMBOL_MAP[symbol] || `OANDA:${symbol}`;

    const widgetDiv = document.createElement("div");
    widgetDiv.className = "tradingview-widget-container__widget";
    widgetDiv.style.height = "100%";
    widgetDiv.style.width = "100%";

    const script = document.createElement("script");
    script.src =
      "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: tvSymbol,
      interval: "5",
      timezone: "Etc/UTC",
      theme: "dark",
      style: "1",
      locale: "ja",
      enable_publishing: false,
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: false,
      backgroundColor: "rgba(13, 17, 23, 1)",
      gridColor: "rgba(48, 54, 61, 0.5)",
      support_host: "https://www.tradingview.com",
    });

    containerRef.current.appendChild(widgetDiv);
    containerRef.current.appendChild(script);
  }, [symbol]);

  return (
    <div className="rounded-xl border border-[var(--border-color)] bg-[var(--background-panel)] overflow-hidden h-[400px] md:h-[550px]">
      <div
        ref={containerRef}
        className="tradingview-widget-container h-full w-full"
      />
    </div>
  );
}
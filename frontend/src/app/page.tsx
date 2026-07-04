/**
 * page.tsx
 * ========
 *
 * このファイルの役割:
 *   アプリのトップページ(ダッシュボード)。
 *   銘柄選択タブ・チャート・シグナルパネルを1画面にまとめる。
 *
 * データの流れ:
 *   1. マウント時に /api/symbols から対応銘柄一覧を取得
 *   2. 選択中の銘柄が変わるたびに /api/signals/{symbol} を取得
 *   3. 30秒ごとに自動でシグナルを再取得する(ポーリング)
 *      ※ バックエンドのスケジューラ(5分おき)とは別に、
 *        フロントエンド側は「画面を見ている間、最新のDB内容を反映する」
 *        役割なので、こちらはもっと短い間隔でも問題ない
 *        (バックエンドはDBから読むだけで外部APIを叩かないため)。
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import SymbolTabs from "@/components/SymbolTabs";
import SignalPanel from "@/components/SignalPanel";
import TradingViewChart from "@/components/TradingViewChart";
import { fetchSymbols, fetchSignal } from "@/services/api";
import { SymbolInfo, SignalData } from "@/types/signal";

const SIGNAL_REFRESH_INTERVAL_MS = 30_000;

export default function Home() {
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [signalData, setSignalData] = useState<SignalData | null>(null);
  const [isLoadingSignal, setIsLoadingSignal] = useState(false);
  const [signalError, setSignalError] = useState<string | null>(null);
  const [symbolsError, setSymbolsError] = useState<string | null>(null);

  useEffect(() => {
    fetchSymbols()
      .then((data) => {
        setSymbols(data);
        if (data.length > 0) {
          setSelectedSymbol(data[0].symbol);
        }
      })
      .catch((err) => {
        setSymbolsError(
          err instanceof Error ? err.message : "銘柄一覧の取得に失敗しました"
        );
      });
  }, []);

  const loadSignal = useCallback((symbol: string) => {
    if (!symbol) return;
    setIsLoadingSignal(true);
    setSignalError(null);
    fetchSignal(symbol)
      .then((data) => {
        setSignalData(data);
      })
      .catch((err) => {
        setSignalError(
          err instanceof Error ? err.message : "シグナルの取得に失敗しました"
        );
        setSignalData(null);
      })
      .finally(() => {
        setIsLoadingSignal(false);
      });
  }, []);

  useEffect(() => {
    if (selectedSymbol) {
      loadSignal(selectedSymbol);
    }
  }, [selectedSymbol, loadSignal]);

  useEffect(() => {
    if (!selectedSymbol) return;
    const intervalId = setInterval(() => {
      loadSignal(selectedSymbol);
    }, SIGNAL_REFRESH_INTERVAL_MS);
    return () => clearInterval(intervalId);
  }, [selectedSymbol, loadSignal]);

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      <header className="border-b border-[var(--border-color)] px-4 py-4 md:px-8">
        <h1 className="text-lg md:text-xl font-bold">FX Signal Dashboard</h1>
        <p className="text-xs text-[var(--foreground-muted)] mt-1">
          半自動売買シグナル支援ツール(最終判断はご自身で行ってください)
        </p>
      </header>

      <main className="px-4 py-6 md:px-8 space-y-6">
        {symbolsError ? (
          <p className="text-[var(--color-sell)] text-sm">{symbolsError}</p>
        ) : (
          <SymbolTabs
            symbols={symbols}
            selectedSymbol={selectedSymbol}
            onSelect={setSelectedSymbol}
          />
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2">
            {selectedSymbol && <TradingViewChart symbol={selectedSymbol} />}
          </div>
          <div className="md:col-span-1">
            <SignalPanel
              data={signalData}
              isLoading={isLoadingSignal}
              error={signalError}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
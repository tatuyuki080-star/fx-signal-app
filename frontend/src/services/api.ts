/**
 * api.ts
 * ======
 *
 * このファイルの役割:
 *   バックエンドAPI(FastAPI)を呼び出す関数をまとめる。
 *
 * なぜ分離する?:
 *   各コンポーネントの中で直接 fetch() を書くと、URLの組み立てや
 *   エラーハンドリングが各所に散らばってしまう。
 *   ここに集約することで、APIの仕様が変わったときの修正箇所を
 *   1ファイルに限定できる。
 */

import { SymbolInfo, SignalData } from "@/types/signal";

/**
 * バックエンドAPIのベースURLを取得する。
 *
 * なぜ動的に組み立てる?:
 *   NEXT_PUBLIC_API_URL を "http://localhost:8000" のように固定すると、
 *   ビルド時にこの値がブラウザ側のコードへ直接埋め込まれてしまう。
 *   その結果、スマホや他のPCから「MacのIPアドレス:3000」で
 *   アクセスした場合でも、ブラウザは常に「localhost:8000」を探しに行き、
 *   各端末自身のlocalhostを見てしまうため繋がらない。
 *
 *   この問題を避けるため、実行時(ブラウザでページが読み込まれた時点)の
 *   window.location.hostname(今アクセスしているホスト名)を使って、
 *   APIのURLを動的に組み立てる。
 *   例: ブラウザが "http://192.168.1.5:3000" を開いていれば、
 *       APIは "http://192.168.1.5:8000" を見に行くようにする。
 */
function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  }

  const hostname = window.location.hostname;
  return `http://${hostname}:8000`;
}

const API_BASE_URL = getApiBaseUrl();

/**
 * 対応銘柄の一覧を取得する。
 */
export async function fetchSymbols(): Promise<SymbolInfo[]> {
  const response = await fetch(`${API_BASE_URL}/api/symbols`);
  if (!response.ok) {
    throw new Error(`銘柄一覧の取得に失敗しました: ${response.status}`);
  }
  return response.json();
}

/**
 * 指定した銘柄の最新シグナルを取得する。
 *
 * 引数:
 *   symbol: アプリ内表記。例: "USDJPY"
 */
export async function fetchSignal(symbol: string): Promise<SignalData> {
  const response = await fetch(`${API_BASE_URL}/api/signals/${symbol}`);
  if (!response.ok) {
    throw new Error(`シグナルの取得に失敗しました(${symbol}): ${response.status}`);
  }
  return response.json();
}
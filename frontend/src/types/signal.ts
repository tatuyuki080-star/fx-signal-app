/**
 * signal.ts
 * =========
 *
 * このファイルの役割:
 *   バックエンドAPI(/api/symbols, /api/signals/{symbol})のレスポンス形を
 *   TypeScriptの型として定義する。
 *
 * なぜ必要?:
 *   型を定義しておくことで、コンポーネント側で
 *   「このプロパティのスペルを間違えた」「存在しないプロパティを使った」
 *   といったミスを、実行前(コンパイル時)に検出できる。
 */

/** 対応銘柄1件分の情報(/api/symbols のレスポンス要素) */
export interface SymbolInfo {
  symbol: string; // 例: "USDJPY"
  display_name: string; // 例: "USD/JPY"
  category: "forex" | "commodity";
}

/** 上位足トレンドの方向。backendのTrendDirection(Enum)と対応 */
export type TrendDirection = "UPTREND" | "DOWNTREND" | "NEUTRAL";

/** シグナルの種類。backendのsignal_typeと対応 */
export type SignalType = "BUY" | "SELL" | "NO_TRADE";

/** シグナル強度ラベル。backendのstrength_labelと対応 */
export type StrengthLabel = "STRONG" | "NORMAL" | "WEAK" | "NONE";

/**
 * シグナル判定の理由(backendのSignalResult.reasonsと対応)。
 * キーは固定だが、将来増える可能性も考慮して文字列キーでも受け付ける形にしている。
 */
export interface SignalReasons {
  higher_tf_trend?: boolean | string;
  rsi_reversal?: boolean;
  macd_cross?: boolean;
  price_vs_sma50?: boolean;
  atr_sufficient?: boolean;
  active_session?: boolean;
  bollinger_position?: boolean;
  [key: string]: boolean | string | undefined;
}

/** /api/signals/{symbol} のレスポンス全体 */
export interface SignalData {
  symbol: string;
  higher_tf_trend: TrendDirection;
  signal_type: SignalType;
  score: number;
  strength_label: StrengthLabel;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  atr_value: number | null;
  reasons: SignalReasons;
}
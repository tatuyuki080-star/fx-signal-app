/**
 * SymbolTabs.tsx
 * ===============
 *
 * このファイルの役割:
 *   ダッシュボード上部に表示する、銘柄を切り替えるためのタブUI。
 *
 * 使い方(親コンポーネントから):
 *   <SymbolTabs
 *     symbols={symbolList}
 *     selectedSymbol={selected}
 *     onSelect={(symbol) => setSelected(symbol)}
 *   />
 */

"use client";

import { SymbolInfo } from "@/types/signal";

interface SymbolTabsProps {
  symbols: SymbolInfo[];
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
}

export default function SymbolTabs({
  symbols,
  selectedSymbol,
  onSelect,
}: SymbolTabsProps) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2">
      {symbols.map((item) => {
        const isSelected = item.symbol === selectedSymbol;
        return (
          <button
            key={item.symbol}
            onClick={() => onSelect(item.symbol)}
            className={`
              shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-colors
              border
              ${
                isSelected
                  ? "bg-[var(--background-panel-hover)] border-[var(--color-normal)] text-[var(--foreground)]"
                  : "bg-[var(--background-panel)] border-[var(--border-color)] text-[var(--foreground-muted)] hover:bg-[var(--background-panel-hover)]"
              }
            `}
          >
            {item.display_name}
          </button>
        );
      })}
    </div>
  );
}
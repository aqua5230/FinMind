"use client";

import { useCallback, useState } from "react";
import { KLinePanel } from "@/components/chart/KLinePanel";
import { AppHeader } from "@/components/layout/AppHeader";
import { StockInfoBar } from "@/components/layout/StockInfoBar";
import { fetchLatestPrice, resolveStockId } from "@/lib/api";
import type { LatestPrice, StockState } from "@/lib/types";

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function getStartDate(): string {
  return "2000-01-01";
}

function getEndDate(): string {
  return formatDate(new Date());
}

export default function Home() {
  const [stock, setStock] = useState<StockState | null>(null);
  const [latestPrice, setLatestPrice] = useState<LatestPrice | null>(null);
  const [error, setError] = useState("");

  const handleSearch = useCallback(async (stockId: string) => {
    if (!stockId.trim()) {
      setError("請輸入股票代號");
      return;
    }
    try {
      const { stockId: id, stockName } = await resolveStockId(stockId);
      const lp = await fetchLatestPrice(id);
      setError("");
      setLatestPrice(lp);
      setStock({ stockId: id, stockName, startDate: getStartDate(), endDate: getEndDate() });
    } catch (err) {
      setLatestPrice(null);
      setError(err instanceof Error ? err.message : "查詢失敗，請稍後再試");
    }
  }, []);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-black">
      <AppHeader onSearch={handleSearch} />

      {stock && (
        <StockInfoBar
          stockId={stock.stockId}
          stockName={stock.stockName}
          startDate={stock.startDate}
          endDate={stock.endDate}
          latestPrice={latestPrice}
        />
      )}

      <main className="flex-1 overflow-hidden">
        {error && (
          <div className="border-b border-[#3A3A3C] px-6 py-3 text-sm text-[#FF453A]">{error}</div>
        )}
        {stock ? (
          <KLinePanel
            stockId={stock.stockId}
            startDate={stock.startDate}
            endDate={stock.endDate}
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-2xl font-semibold tracking-tight text-white">K 線圖</p>
          </div>
        )}
      </main>
    </div>
  );
}

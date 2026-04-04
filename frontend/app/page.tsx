"use client";

import { useCallback, useState } from "react";
import { KLinePanel } from "@/components/chart/KLinePanel";
import { AppHeader } from "@/components/layout/AppHeader";
import { StockInfoBar } from "@/components/layout/StockInfoBar";
import { fetchStockName } from "@/lib/api";
import type { StockState } from "@/lib/types";

const START_DATE = "2000-01-01";

function getEndDate(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function Home() {
  const [stock, setStock] = useState<StockState | null>(null);
  const [error, setError] = useState("");

  const handleSearch = useCallback(async (stockId: string) => {
    const id = stockId.trim().toUpperCase();
    if (!id) {
      setError("請輸入股票代號");
      return;
    }
    try {
      const stockName = await fetchStockName(id);
      setError("");
      setStock({ stockId: id, stockName, startDate: START_DATE, endDate: getEndDate() });
    } catch {
      setError("查詢失敗，請稍後再試");
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

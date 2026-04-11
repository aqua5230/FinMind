"use client";

import { useCallback, useState } from "react";
import {
  setChartInitialActiveIndicators,
  type IndicatorKey,
} from "@/components/chart/CandlestickChart";
import { KLinePanel } from "@/components/chart/KLinePanel";
import { AppHeader } from "@/components/layout/AppHeader";
import { StockInfoBar } from "@/components/layout/StockInfoBar";
import { ScanPanel } from "@/components/ui/ScanPanel";
import { fetchLatestPrice, fetchScan, resolveStockId, type ScanResult } from "@/lib/api";
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

const SCAN_INDICATORS: IndicatorKey[] = ["BOLL", "MACD", "RSI"];

export default function Home() {
  const [stock, setStock] = useState<StockState | null>(null);
  const [latestPrice, setLatestPrice] = useState<LatestPrice | null>(null);
  const [error, setError] = useState("");
  const [isScanning, setIsScanning] = useState(false);
  const [isScanPanelOpen, setIsScanPanelOpen] = useState(false);
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [chartSessionKey, setChartSessionKey] = useState(0);

  const loadStock = useCallback(
    async (stockId: string, stockName: string, activeIndicators: IndicatorKey[] = []) => {
      const lp = await fetchLatestPrice(stockId);
      setChartInitialActiveIndicators(activeIndicators);
      setLatestPrice(lp);
      setStock({ stockId, stockName, startDate: getStartDate(), endDate: getEndDate() });
      setChartSessionKey((current) => current + 1);
    },
    [],
  );

  const handleSearch = useCallback(async (value: string) => {
    if (!value.trim()) {
      setError("請輸入股票代號");
      return;
    }
    try {
      const { stockId, stockName } = await resolveStockId(value);
      await loadStock(stockId, stockName);
      setError("");
    } catch (err) {
      setLatestPrice(null);
      setError(err instanceof Error ? err.message : "查詢失敗，請稍後再試");
    }
  }, [loadStock]);

  const handleScan = useCallback(async () => {
    setIsScanning(true);
    setIsScanPanelOpen(true);
    setError("");

    try {
      const scan = await fetchScan();
      setScanResults(scan.results);
    } catch (err) {
      setScanResults([]);
      setError(err instanceof Error ? err.message : "掃描失敗，請稍後再試");
    } finally {
      setIsScanning(false);
    }
  }, []);

  const handleSelectScanResult = useCallback(async (result: ScanResult) => {
    try {
      await loadStock(result.stock_id, result.stock_name, SCAN_INDICATORS);
      setError("");
      setIsScanPanelOpen(false);
    } catch (err) {
      setLatestPrice(null);
      setError(err instanceof Error ? err.message : "查詢失敗，請稍後再試");
    }
  }, [loadStock]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-black">
      <AppHeader onSearch={handleSearch} onScan={handleScan} isScanning={isScanning} />

      {isScanPanelOpen && (
        <ScanPanel
          isLoading={isScanning}
          results={scanResults}
          onSelect={handleSelectScanResult}
        />
      )}

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
            key={`${stock.stockId}-${chartSessionKey}`}
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

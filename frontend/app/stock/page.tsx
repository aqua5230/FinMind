"use client";

import React, { useState, useEffect, useCallback, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  setChartInitialActiveIndicators,
  type IndicatorKey,
} from "@/components/chart/CandlestickChart";
import { KLinePanel } from "@/components/chart/KLinePanel";
import { StockInfoBar } from "@/components/layout/StockInfoBar";
import { fetchLatestPrice } from "@/lib/api";
import type { LatestPrice } from "@/lib/types";

const C_SYS = 'text-[#00E5FF]';
const C_BORDER = 'border-[#222222]';

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function StockPageContent() {
  const searchParams = useSearchParams();
  const stockId = searchParams.get('id') ?? '';
  const stockName = searchParams.get('name') ?? stockId;
  const signalDate = searchParams.get('signal') ?? undefined;
  const indicators = (searchParams.get('indicators') ?? '').split(',').filter(Boolean) as IndicatorKey[];

  const [latestPrice, setLatestPrice] = useState<LatestPrice | null>(null);
  const [sessionKey] = useState(0);
  const startDate = '2000-01-01';
  const endDate = formatDate(new Date());

  useEffect(() => {
    if (!stockId) return;
    setChartInitialActiveIndicators(indicators.length > 0 ? indicators : []);
    fetchLatestPrice(stockId).then(setLatestPrice).catch(() => {});
  }, [stockId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!stockId) {
    return (
      <div className="h-screen w-full bg-black flex items-center justify-center text-[#555] font-mono text-[17px]">
        無效的股票代號
      </div>
    );
  }

  return (
    <div className="h-screen w-full bg-black flex flex-col overflow-hidden font-mono">
      {/* 頂部列 */}
      <header className={`flex items-center justify-between px-4 h-[40px] shrink-0 border-b ${C_BORDER} bg-[#050505]`}>
        <button
          type="button"
          onClick={() => window.close()}
          className={`text-[15px] ${C_SYS} hover:opacity-70 cursor-pointer mr-4`}
        >
          ← 關閉
        </button>
        <span className="text-[15px] text-[#555] tracking-widest">量化終端_v2.6</span>
      </header>

      {/* 股票資訊列 */}
      <StockInfoBar
        stockId={stockId}
        stockName={stockName}
        startDate={startDate}
        endDate={endDate}
        latestPrice={latestPrice}
      />

      {/* K 線圖主體 */}
      <div className="flex-1 overflow-hidden">
        <KLinePanel
          key={`${stockId}-${sessionKey}`}
          stockId={stockId}
          startDate={startDate}
          endDate={endDate}
          signalDate={signalDate}
        />
      </div>
    </div>
  );
}

export default function StockPage() {
  return (
    <Suspense fallback={
      <div className="h-screen w-full bg-black flex items-center justify-center text-[#555] font-mono text-[17px]">
        載入中…
      </div>
    }>
      <StockPageContent />
    </Suspense>
  );
}

"use client";

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  setChartInitialActiveIndicators,
  type IndicatorKey,
} from "@/components/chart/CandlestickChart";
import { KLinePanel } from "@/components/chart/KLinePanel";
import { StockInfoBar } from "@/components/layout/StockInfoBar";
import { fetchLatestPrice, fetchRealtimeBar } from "@/lib/api";
import type { LatestPrice } from "@/lib/types";

const C_SYS = 'text-[#00E5FF]';
const C_BORDER = 'border-[#222222]';

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function isTwTradingHours(date = new Date()): boolean {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Taipei',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
    .formatToParts(date)
    .reduce<Record<string, string>>((acc, part) => {
      acc[part.type] = part.value;
      return acc;
    }, {});

  if (parts.weekday === 'Sat' || parts.weekday === 'Sun') return false;

  const hour = Number(parts.hour);
  const minute = Number(parts.minute);
  const minutes = hour * 60 + minute;

  return minutes >= 9 * 60 && minutes <= 14 * 60;
}

function StockPageContent() {
  const searchParams = useSearchParams();
  const stockId = searchParams.get('id') ?? '';
  const stockName = searchParams.get('name') ?? stockId;
  const signalDate = searchParams.get('signal') ?? undefined;
  const indicators = (searchParams.get('indicators') ?? '').split(',').filter(Boolean) as IndicatorKey[];

  const [latestPrice, setLatestPrice] = useState<LatestPrice | null>(null);
  const [prevClose, setPrevClose] = useState<{ stockId: string; value: number } | null>(null);
  const [sessionKey] = useState(0);
  const startDate = '2000-01-01';
  const endDate = formatDate(new Date());

  useEffect(() => {
    if (!stockId) return;
    let cancelled = false;

    setChartInitialActiveIndicators(indicators.length > 0 ? indicators : []);
    setPrevClose(null);
    fetchLatestPrice(stockId)
      .then((price) => {
        if (cancelled) return;
        setLatestPrice(price);
        setPrevClose(price ? { stockId, value: price.close - price.change } : null);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [stockId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const prevCloseValue = prevClose?.stockId === stockId ? prevClose.value : null;
    if (!stockId || prevCloseValue === null || !isTwTradingHours()) return;

    let cancelled = false;

    const updateRealtimePrice = async () => {
      if (!isTwTradingHours()) return;

      const realtimeBar = await fetchRealtimeBar(stockId);
      if (cancelled || !realtimeBar) return;

      const realtimeClose = realtimeBar.close;
      const change = realtimeClose - prevCloseValue;
      const changePct = prevCloseValue === 0 ? 0 : (change / prevCloseValue) * 100;

      setLatestPrice({ close: realtimeClose, change, changePct });
    };

    updateRealtimePrice();
    const intervalId = window.setInterval(updateRealtimePrice, 30_000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [stockId, prevClose]);

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

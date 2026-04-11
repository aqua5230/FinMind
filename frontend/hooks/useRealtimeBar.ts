"use client";

import { useEffect, useState } from "react";
import type { KLineData } from "klinecharts";
import { fetchRealtimeBar } from "@/lib/api";

function isTwTradingHours(): boolean {
  const now = new Date();
  const twStr = now.toLocaleString("en-US", { timeZone: "Asia/Taipei" });
  const tw = new Date(twStr);
  const day = tw.getDay();
  if (day === 0 || day === 6) return false;
  const total = tw.getHours() * 60 + tw.getMinutes();
  return total >= 9 * 60 && total <= 14 * 60;
}

export function useRealtimeBar(stockId: string, enabled: boolean): KLineData | null {
  const [bar, setBar] = useState<KLineData | null>(null);

  useEffect(() => {
    if (!enabled) return;

    async function fetchAndSet() {
      if (!isTwTradingHours()) return;
      const raw = await fetchRealtimeBar(stockId);
      if (!raw) return;
      const parts = raw.date.split("-").map(Number);
      const ts = Date.UTC(parts[0], parts[1] - 1, parts[2]);
      const kbar: KLineData = {
        timestamp: ts,
        open: raw.open,
        high: raw.high,
        low: raw.low,
        close: raw.close,
        volume: raw.volume,
      };
      setBar(kbar);
    }

    void fetchAndSet();
    const id = setInterval(() => void fetchAndSet(), 60_000);
    return () => clearInterval(id);
  }, [stockId, enabled]);

  return bar;
}

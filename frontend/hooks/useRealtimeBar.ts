"use client";

import { useEffect, useState } from "react";
import type { KLineData } from "klinecharts";
import { API_URL } from "@/lib/api";

type RealtimeTrade = {
  stock_id?: string;
  price?: number;
  size?: number;
  time?: string | null;
};

const MAX_RECONNECT_ATTEMPTS = 3;
const RECONNECT_DELAY_MS = 3_000;

function isTwTradingHours(): boolean {
  const now = new Date();
  const twStr = now.toLocaleString("en-US", { timeZone: "Asia/Taipei" });
  const tw = new Date(twStr);
  const day = tw.getDay();
  if (day === 0 || day === 6) return false;
  const total = tw.getHours() * 60 + tw.getMinutes();
  return total >= 9 * 60 && total <= 14 * 60;
}

function getRealtimeWsUrl(stockId: string): string {
  const baseUrl = API_URL || (typeof window === "undefined" ? "" : window.location.origin);
  return `${baseUrl.replace(/^http/, "ws")}/ws/realtime/${encodeURIComponent(stockId)}`;
}

function getTwDateTimestamp(): number {
  const twStr = new Date().toLocaleString("en-US", { timeZone: "Asia/Taipei" });
  const tw = new Date(twStr);
  return Date.UTC(tw.getFullYear(), tw.getMonth(), tw.getDate());
}

export function useRealtimeBar(stockId: string, enabled: boolean): KLineData | null {
  const [bar, setBar] = useState<KLineData | null>(null);

  useEffect(() => {
    if (!enabled || !stockId || !isTwTradingHours()) return;

    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let reconnectAttempts = 0;
    let closed = false;

    const connect = () => {
      if (closed || !isTwTradingHours()) return;

      socket = new WebSocket(getRealtimeWsUrl(stockId));

      socket.onopen = () => {
        reconnectAttempts = 0;
      };

      socket.onmessage = (event) => {
        let trade: RealtimeTrade;
        try {
          trade = JSON.parse(event.data) as RealtimeTrade;
        } catch {
          return;
        }

        const price = typeof trade.price === "number" ? trade.price : null;
        if (price === null) return;

        const size = typeof trade.size === "number" ? trade.size : 0;
        const timestamp = getTwDateTimestamp();

        setBar((current) => {
          const isSameDay = current?.timestamp === timestamp;
          return {
            timestamp,
            open: isSameDay ? current.open : price,
            high: isSameDay ? Math.max(current.high, price) : price,
            low: isSameDay ? Math.min(current.low, price) : price,
            close: price,
            volume: (isSameDay ? current.volume ?? 0 : 0) + size,
          };
        });
      };

      socket.onclose = () => {
        if (closed || !isTwTradingHours() || reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) return;
        reconnectAttempts += 1;
        reconnectTimer = window.setTimeout(connect, RECONNECT_DELAY_MS);
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, [stockId, enabled]);

  return bar;
}

"use client";

import { useEffect, useState } from "react";
import { fetchPrices } from "@/lib/api";
import type { StockBar } from "@/lib/types";

type UseStockDataResult = {
  data: StockBar[];
  loading: boolean;
  error: string | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isBar(value: unknown): value is StockBar {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.date === "string" &&
    typeof value.open === "number" &&
    typeof value.high === "number" &&
    typeof value.low === "number" &&
    typeof value.close === "number" &&
    typeof value.volume === "number"
  );
}

function sortBars(bars: StockBar[]): StockBar[] {
  return [...bars].sort((left, right) => left.date.localeCompare(right.date));
}

export function useStockData(stockId: string, startDate: string, endDate: string): UseStockDataResult {
  const [data, setData] = useState<StockBar[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadPrices() {
      setLoading(true);
      setError(null);

      try {
        const prices = (await fetchPrices(stockId, startDate, endDate, {
          signal: controller.signal,
        })) as unknown;
        if (!Array.isArray(prices) || !prices.every(isBar)) {
          throw new Error("Invalid payload");
        }

        if (controller.signal.aborted) {
          return;
        }

        setData(sortBars(prices));
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }

        console.error("Failed to load stock prices", {
          stockId,
          startDate,
          endDate,
          error,
        });
        setData([]);
        setError("無法載入價格資料");
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadPrices();

    return () => controller.abort();
  }, [endDate, startDate, stockId]);

  return { data, loading, error };
}

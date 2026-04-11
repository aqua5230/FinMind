import type { LatestPrice, PriceResponse, StockBar } from "@/lib/types";

export type ScanResult = {
  stock_id: string;
  stock_name: string;
  signal_date: string;
  days_ago: number;
};

export type ScanResponse = {
  scanned_at: string;
  total_scanned: number;
  results: ScanResult[];
};

function normalizeApiUrl(value: string | undefined): string {
  if (!value) {
    return "";
  }

  return value.endsWith("/") ? value.slice(0, -1) : value;
}

const API_URL = normalizeApiUrl(process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.API_BASE_URL);

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string };
    return payload.detail ?? payload.message ?? response.statusText;
  } catch {
    return response.statusText;
  }
}

let stocksCache: { stock_id: string; name: string }[] | null = null;

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_URL}${path}`;
  let response: Response;

  try {
    response = await fetch(url, options);
  } catch (error) {
    console.error("API request failed before response", {
      url,
      error,
    });
    throw error;
  }

  if (!response.ok) {
    const detail = await readErrorMessage(response);
    console.error("API request failed", {
      url,
      status: response.status,
      detail,
    });
    throw new Error(`API error ${response.status}: ${detail}`);
  }

  return (await response.json()) as T;
}

export async function fetchPrices(
  stockId: string,
  startDate: string,
  endDate: string,
  options?: RequestInit,
): Promise<StockBar[]> {
  const query = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });
  const response = await apiFetch<PriceResponse>(`/api/price/${stockId}?${query.toString()}`, options);
  return response.prices;
}

export async function fetchStockName(stockId: string): Promise<string> {
  if (!stocksCache) {
    try {
      stocksCache = await apiFetch<{ stock_id: string; name: string }[]>("/api/stocks");
    } catch {
      stocksCache = null;
    }
  }
  const match = stocksCache?.find((s) => s.stock_id === stockId);
  return match?.name ?? stockId;
}

export async function fetchLatestPrice(stockId: string): Promise<LatestPrice | null> {
  const endDate = new Date().toISOString().slice(0, 10);
  const startDate = new Date(Date.now() - 14 * 86400000).toISOString().slice(0, 10);
  try {
    const bars = await fetchPrices(stockId, startDate, endDate);
    if (bars.length < 2) return null;
    const last = bars[bars.length - 1];
    const prev = bars[bars.length - 2];
    const change = last.close - prev.close;
    const changePct = (change / prev.close) * 100;
    return { close: last.close, change, changePct };
  } catch {
    return null;
  }
}

export async function fetchScan(): Promise<ScanResponse> {
  return apiFetch<ScanResponse>("/api/scan");
}

function normalizeInput(input: string): string {
  return input
    .replace(/[０-９]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xFEE0))
    .trim()
    .toUpperCase();
}

export async function resolveStockId(
  input: string,
): Promise<{ stockId: string; stockName: string }> {
  const normalized = normalizeInput(input);
  if (!stocksCache) {
    try {
      stocksCache = await apiFetch<{ stock_id: string; name: string }[]>("/api/stocks");
    } catch {
      stocksCache = null;
    }
  }
  const byId = stocksCache?.find((s) => s.stock_id === normalized);
  if (byId) return { stockId: byId.stock_id, stockName: byId.name };
  const byName =
    stocksCache?.find((s) => s.name === input.trim()) ??
    stocksCache?.find((s) => s.name.includes(input.trim()));
  if (byName) return { stockId: byName.stock_id, stockName: byName.name };
  throw new Error("找不到此股票");
}

export { API_URL };

export async function fetchRealtimeBar(stockId: string): Promise<StockBar | null> {
  try {
    const data = await apiFetch<StockBar>(`/api/realtime/${stockId}`);
    return data;
  } catch {
    return null;
  }
}

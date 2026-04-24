import type { LatestPrice, PriceResponse, StockBar } from "@/lib/types";

const API_URL = "";

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

function isTwTradingHours(): boolean {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Taipei',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
    .formatToParts(new Date())
    .reduce<Record<string, string>>((acc, p) => { acc[p.type] = p.value; return acc; }, {});
  if (parts.weekday === 'Sat' || parts.weekday === 'Sun') return false;
  const minutes = Number(parts.hour) * 60 + Number(parts.minute);
  return minutes >= 9 * 60 && minutes <= 14 * 60;
}

export async function fetchLatestPrice(stockId: string): Promise<LatestPrice | null> {
  // 盤中：用 TWSE 即時 API，取得當下成交價與昨收
  if (isTwTradingHours()) {
    try {
      const rt = await apiFetch<{
        close: number;
        prev_close: number | null;
      }>(`/api/realtime/${encodeURIComponent(stockId)}`);
      if (rt.prev_close != null && rt.prev_close > 0) {
        const change = rt.close - rt.prev_close;
        const changePct = (change / rt.prev_close) * 100;
        return { close: rt.close, change, changePct };
      }
    } catch {
      // fallback to historical below
    }
  }

  // 盤後或即時抓取失敗：用歷史 K 線
  const endDate = new Date().toISOString().slice(0, 10);
  const startDate = new Date(Date.now() - 5 * 86400000).toISOString().slice(0, 10);
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
    stocksCache?.find((s) => s.name.startsWith(input.trim())) ??
    stocksCache?.find((s) => s.name.includes(input.trim()));
  if (byName) return { stockId: byName.stock_id, stockName: byName.name };
  throw new Error("找不到此股票");
}

export type RevenueScanResult = {
  stock_id: string;
  stock_name: string;
  revenue_ym: string;
  revenue_yoy: number;
  rank: number;
};

export type RevenueScanResponse = {
  scanned_at: string;
  total_scanned: number;
  market_filter: string;
  results: RevenueScanResult[];
};

export async function fetchRevenueScan(): Promise<RevenueScanResponse> {
  return apiFetch<RevenueScanResponse>("/api/revenue-scan");
}

export interface PairScanResult {
  stock_a: string;
  stock_b: string;
  correlation: number;
  deviation: number;
  suggestion: string;
  a_return_5d: number;
  b_return_5d: number;
}

export interface PairScanResponse {
  pairs: PairScanResult[];
  computed_at: string;
  stock_count: number;
}

export async function fetchPairScan(): Promise<PairScanResponse> {
  return apiFetch<PairScanResponse>("/api/pair-scan");
}

export type InstitutionScanResult = {
  stock_id: string;
  stock_name: string;
  foreign_consecutive_buy: number;
  trust_buy_days: number;
  foreign_net_20d: number;
};

export type InstitutionScanResponse = {
  scanned_at: string;
  total_scanned: number;
  results: InstitutionScanResult[];
};

export async function fetchInstitutionScan(): Promise<InstitutionScanResponse> {
  return apiFetch<InstitutionScanResponse>("/api/institution-scan");
}

export type DispositionScanResult = {
  stock_id: string;
  stock_name: string;
  disposition_start: string;
  disposition_end: string;
  days_to_release: number;
  price_change_during: number;
};

export type DispositionScanResponse = {
  scanned_at: string;
  total_scanned: number;
  results: DispositionScanResult[];
};

export async function fetchDispositionScan(): Promise<DispositionScanResponse> {
  return apiFetch<DispositionScanResponse>("/api/disposition-scan");
}

export type ChipsScanResult = {
  stock_id: string;
  stock_name: string;
  change_pct: number;
  volume_lot: number;
  volume_ratio: number;
  net_1d: number;
  net_10d: number;
  net_20d: number;
  ma20_deviation: number;
};

export type ChipsScanResponse = {
  scanned_at: string;
  total_scanned: number;
  results: ChipsScanResult[];
};

export async function fetchChipsScan(): Promise<ChipsScanResponse> {
  return apiFetch<ChipsScanResponse>("/api/chips-scan");
}

export type CbScanResult = {
  bond_id: string;
  stock_id: string;
  stock_name: string;
  put_date: string;
  put_price: number;
  cb_price: number;
  days_to_put: number;
  annualized_return: number;
  guarantor: string;
};

export type CbScanResponse = {
  scanned_at: string;
  total_scanned: number;
  results: CbScanResult[];
  error?: string | null;
};

export async function fetchCbScan(): Promise<CbScanResponse> {
  return apiFetch<CbScanResponse>("/api/cb-scan");
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

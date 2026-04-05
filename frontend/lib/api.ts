import type { PriceResponse, StockBar } from "@/lib/types";

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

export { API_URL };

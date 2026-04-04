const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let stocksCache: { stock_id: string; name: string }[] | null = null;

export async function fetchStockName(stockId: string): Promise<string> {
  if (!stocksCache) {
    const res = await fetch(`${API_URL}/api/stocks`);
    if (res.ok) {
      stocksCache = await res.json();
    }
  }
  const match = stocksCache?.find((s) => s.stock_id === stockId);
  return match?.name ?? stockId;
}

export { API_URL };

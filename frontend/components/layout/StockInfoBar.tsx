import type { LatestPrice } from "@/lib/types";

type Props = {
  stockId: string;
  stockName: string;
  startDate: string;
  endDate: string;
  latestPrice?: LatestPrice | null;
};

export function StockInfoBar({ stockId, stockName, latestPrice }: Props) {
  const color = !latestPrice
    ? "#8E8E93"
    : latestPrice.change > 0
      ? "#30D158"
      : latestPrice.change < 0
        ? "#FF453A"
        : "#8E8E93";
  const arrow = !latestPrice
    ? ""
    : latestPrice.change > 0
      ? " ↑"
      : latestPrice.change < 0
        ? " ↓"
        : " —";

  return (
    <div className="flex h-11 items-center border-b border-[#3A3A3C] bg-[#1C1C1E] px-6">
      <div className="flex items-center gap-3">
        <span className="rounded-md bg-[#2C2C2E] px-2.5 py-0.5 text-xs font-medium text-[#8E8E93]">
          {stockId}
        </span>
        <span className="text-base font-semibold tracking-tight text-white">{stockName}</span>
      </div>
      {latestPrice && (
        <div className="ml-auto flex flex-col items-end">
          <span className="text-sm font-semibold text-white">
            {latestPrice.close.toLocaleString("zh-TW", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}{" "}
            TWD
          </span>
          <span className="text-xs" style={{ color }}>
            {latestPrice.change >= 0 ? "+" : ""}
            {latestPrice.change.toFixed(2)} ({Math.abs(latestPrice.changePct).toFixed(2)}%)
            {arrow}
          </span>
        </div>
      )}
    </div>
  );
}

import type { LatestPrice } from "@/lib/types";

type Props = {
  stockId: string;
  stockName: string;
  startDate: string;
  endDate: string;
  latestPrice?: LatestPrice | null;
};

export function StockInfoBar({ stockId, stockName, latestPrice }: Props) {
  const changeBadgeClass = !latestPrice
    ? "bg-[#8E8E93]"
    : latestPrice.change > 0
      ? "bg-[#30D158]"
      : latestPrice.change < 0
        ? "bg-[#FF453A]"
        : "bg-[#8E8E93]";
  const changeSymbol = !latestPrice
    ? "—"
    : latestPrice.change > 0
      ? "▲"
      : latestPrice.change < 0
        ? "▼"
        : "—";

  return (
    <div className="flex h-auto min-h-[44px] items-center border-b border-[#3A3A3C] bg-[#1C1C1E] px-6 py-1.5">
      <div className="flex items-center gap-3">
        <span className="rounded-md bg-[#2C2C2E] px-2.5 py-0.5 text-xs font-medium text-[#8E8E93]">
          {stockId}
        </span>
        <span className="text-base font-semibold tracking-tight text-white">{stockName}</span>
        {latestPrice && (
          <>
            <span className="h-4 w-px bg-[#3A3A3C]" />
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-bold text-white">
                {latestPrice.close.toLocaleString("zh-TW", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
              <span
                className={`${changeBadgeClass} rounded-md px-2.5 py-1 text-sm font-semibold text-white`}
              >
                {changeSymbol}{" "}
                {latestPrice.change >= 0 ? "+" : ""}
                {latestPrice.change.toFixed(2)} ({Math.abs(latestPrice.changePct).toFixed(2)}%)
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

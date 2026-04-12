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
    ? "bg-[#222] text-[#666]"
    : latestPrice.change > 0
      ? "bg-[#003319] text-[#00FF66]"
      : latestPrice.change < 0
        ? "bg-[#330008] text-[#FF003C]"
        : "bg-[#222] text-[#666]";
  const changeSymbol = !latestPrice
    ? "—"
    : latestPrice.change > 0
      ? "▲"
      : latestPrice.change < 0
        ? "▼"
        : "—";

  return (
    <div className="flex h-auto min-h-[44px] items-center border-b border-[#222222] bg-[#050505] px-6 py-1.5">
      <div className="flex items-center gap-3">
        <span className="rounded-md bg-[#111] px-2.5 py-0.5 text-sm font-medium text-[#00E5FF]">
          {stockId}
        </span>
        <span className="text-lg font-semibold tracking-tight text-white">{stockName}</span>
        {latestPrice && (
          <>
            <span className="h-4 w-px bg-[#333]" />
            <div className="flex items-baseline gap-2">
              <span className="text-5xl font-bold text-white">
                {latestPrice.close.toLocaleString("zh-TW", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
              <span
                className={`${changeBadgeClass} rounded-md px-2.5 py-1 text-base font-semibold`}
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

type Props = {
  stockId: string;
  stockName: string;
  startDate: string;
  endDate: string;
};

export function StockInfoBar({ stockId, stockName }: Props) {
  return (
    <div className="flex h-11 items-center border-b border-[#3A3A3C] bg-[#1C1C1E] px-6">
      <div className="flex items-center gap-3">
        <span className="rounded-md bg-[#2C2C2E] px-2.5 py-0.5 text-xs font-medium text-[#8E8E93]">
          {stockId}
        </span>
        <span className="text-base font-semibold tracking-tight text-white">{stockName}</span>
      </div>

      <div className="ml-auto" />
    </div>
  );
}

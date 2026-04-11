"use client";

import type { ScanResult } from "@/lib/api";

type Props = {
  isLoading: boolean;
  results: ScanResult[];
  onSelect: (result: ScanResult) => void;
};

function formatDaysAgo(daysAgo: number): string {
  return `${daysAgo} 天前`;
}

export function ScanPanel({ isLoading, results, onSelect }: Props) {
  return (
    <section className="border-b border-[#3A3A3C] bg-[#1C1C1E] px-6 py-3">
      {isLoading ? (
        <p className="text-sm text-[#8E8E93]">掃描中...</p>
      ) : results.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {results.map((result) => (
            <button
              key={`${result.stock_id}-${result.signal_date}`}
              type="button"
              onClick={() => onSelect(result)}
              className="flex min-h-9 items-center gap-2 rounded-md bg-[#2C2C2E] px-3 py-2 text-left text-sm text-white transition hover:bg-[#3A3A3C] focus:outline focus:outline-1 focus:outline-[#0A84FF]"
            >
              <span className="rounded-md bg-black px-2 py-0.5 text-xs font-semibold text-white">
                {result.stock_id}
              </span>
              <span className="font-medium">{result.stock_name}</span>
              <span className="text-xs text-[#8E8E93]">
                {result.signal_date}（{formatDaysAgo(result.days_ago)}）
              </span>
            </button>
          ))}
        </div>
      ) : (
        <p className="text-sm text-[#8E8E93]">今日無符合訊號的股票</p>
      )}
    </section>
  );
}

"use client";

import { SearchInput } from "@/components/ui/SearchInput";

type Props = {
  onSearch: (stockId: string) => void | Promise<void>;
  onScan: () => void | Promise<void>;
  isScanning?: boolean;
  searchValue: string;
  onSearchChange: (value: string) => void;
};

export function AppHeader({
  onSearch,
  onScan,
  isScanning = false,
  searchValue,
  onSearchChange,
}: Props) {
  return (
    <header className="flex h-[52px] items-center border-b border-[#3A3A3C] bg-black px-6">
      <div className="w-72" aria-hidden="true" />
      <div className="flex flex-1 justify-center">
        <SearchInput
          value={searchValue}
          onChange={onSearchChange}
          onEnter={onSearch}
          className="w-72"
        />
      </div>
      <div className="flex w-72 justify-end">
        <button
          type="button"
          onClick={onScan}
          disabled={isScanning}
          className="rounded-md bg-[#2C2C2E] px-3 py-1.5 text-sm text-white transition hover:bg-[#3A3A3C] disabled:cursor-wait disabled:opacity-70"
        >
          {isScanning ? "掃描中..." : "掃描"}
        </button>
      </div>
    </header>
  );
}

"use client";

import { useState } from "react";
import { SearchInput } from "@/components/ui/SearchInput";

type Props = {
  onSearch: (stockId: string) => void | Promise<void>;
};

export function AppHeader({ onSearch }: Props) {
  const [searchValue, setSearchValue] = useState("");

  return (
    <header className="flex h-[52px] items-center border-b border-[#3A3A3C] bg-black px-6">
      <div className="w-72" aria-hidden="true" />
      <div className="flex flex-1 justify-center">
        <SearchInput
          value={searchValue}
          onChange={setSearchValue}
          onEnter={onSearch}
          className="w-72"
        />
      </div>
      <div className="w-72" aria-hidden="true" />
    </header>
  );
}

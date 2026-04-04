"use client";

import type { KeyboardEvent } from "react";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onEnter: (value: string) => void | Promise<void>;
  placeholder?: string;
  className?: string;
};

export function SearchInput({
  value,
  onChange,
  onEnter,
  placeholder = "搜尋股票代號",
  className = "",
}: Props) {
  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      onEnter(value);
    }
  }

  return (
    <input
      value={value}
      onChange={(event) => onChange(event.currentTarget.value)}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      className={`rounded-full bg-[#1C1C1E] px-5 py-2 text-base text-white outline-none ring-0 placeholder:text-[#6B6B70] focus:ring-1 focus:ring-[#0A84FF] ${className}`.trim()}
    />
  );
}

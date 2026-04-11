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
    <div className={`relative ${className}`.trim()}>
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6B6B70]"
        viewBox="0 0 16 16"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M7.25 12.5a5.25 5.25 0 1 1 0-10.5 5.25 5.25 0 0 1 0 10.5ZM11 11l3 3"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <input
        value={value}
        onChange={(event) => onChange(event.currentTarget.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="w-full rounded-full bg-[#1C1C1E] py-2 pl-10 pr-5 text-base text-white outline-none ring-0 placeholder:text-[#6B6B70] focus:ring-1 focus:ring-[#0A84FF]"
      />
    </div>
  );
}

import type { ReactNode } from "react";

type Props = {
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
  className?: string;
};

export function PillButton({ active = false, onClick, children, className = "" }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-sm transition ${
        active
          ? "bg-[#3A3A3C] text-white"
          : "bg-transparent text-[#8E8E93] hover:bg-[#2C2C2E]"
      } ${className}`.trim()}
    >
      {children}
    </button>
  );
}

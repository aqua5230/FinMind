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
          ? "bg-[#1a1a1a] text-[#00E5FF]"
          : "bg-transparent text-[#555] hover:bg-[#111]"
      } ${className}`.trim()}
    >
      {children}
    </button>
  );
}

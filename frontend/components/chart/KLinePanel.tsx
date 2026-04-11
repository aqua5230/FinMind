"use client";

import {
  CandlestickChart,
  ChartControlsProvider,
  normalizeMaPeriod,
  useChartControls,
  type ChartType,
  type IndicatorKey,
} from "@/components/chart/CandlestickChart";
import { PillButton } from "@/components/ui/PillButton";

type Props = { stockId: string; startDate: string; endDate: string; signalDate?: string };
const TEXT_TOGGLE_BUTTON_CLASS = "rounded-md px-3 py-1 text-xs transition";
const INDICATOR_TOGGLES: IndicatorKey[] = ["BOLL", "MACD", "RSI"];

function getChartTypeButtonClass(active: boolean) {
  return [
    TEXT_TOGGLE_BUTTON_CLASS,
    active ? "bg-[#3A3A3C] text-white" : "bg-transparent text-[#8E8E93] hover:text-white",
  ].join(" ");
}

function ChartControls() {
  const {
    period,
    setPeriod,
    chartType,
    setChartType,
    maPeriods,
    setMaPeriods,
    maInput,
    setMaInput,
    activeIndicators,
    setActiveIndicators,
  } = useChartControls();

  function addMaPeriod() {
    const normalized = normalizeMaPeriod(maInput);
    if (normalized === null) {
      setMaInput("");
      return;
    }

    setMaPeriods((current) => {
      if (current.includes(normalized)) {
        return current;
      }
      return [...current, normalized].sort((left, right) => left - right);
    });
    setMaInput("");
  }

  function removeMaPeriod(target: number) {
    setMaPeriods((current) => current.filter((value) => value !== target));
  }

  function toggleIndicator(indicator: IndicatorKey) {
    setActiveIndicators((current) =>
      current.includes(indicator)
        ? current.filter((value) => value !== indicator)
        : [...current, indicator],
    );
  }

  return (
    <div className="flex items-center gap-4 border-b border-[#3A3A3C] bg-[#1C1C1E] px-4 py-2 overflow-x-auto">
      <div className="flex gap-1">
        {([
          { key: "D", label: "日" },
          { key: "W", label: "週" },
          { key: "M", label: "月" },
        ] as const).map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setPeriod(key)}
            className={getChartTypeButtonClass(period === key)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mx-1 h-3.5 w-px bg-[#636366]" />

      <div className="flex gap-1">
        {([
          { key: "candle_solid", label: "實心" },
          { key: "candle_stroke", label: "空心" },
        ] as const).map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setChartType(key as ChartType)}
            className={getChartTypeButtonClass(chartType === key)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mx-1 h-3.5 w-px bg-[#636366]" />

      <div className="flex flex-wrap items-center gap-1">
        {INDICATOR_TOGGLES.map((indicator) => (
          <PillButton
            key={indicator}
            active={activeIndicators.includes(indicator)}
            onClick={() => toggleIndicator(indicator)}
            className="h-7 px-3 py-0 text-xs"
          >
            {indicator}
          </PillButton>
        ))}
      </div>

      <div className="mx-1 h-3.5 w-px bg-[#636366]" />

      <div className="flex flex-wrap items-center gap-1.5">
        {maPeriods.map((value) => (
          <span
            key={value}
            className="inline-flex items-center gap-1 rounded-md bg-[#2C2C2E] px-2 py-0.5 text-xs font-medium text-[#8E8E93]"
          >
            {`MA${value}`}
            <button
              type="button"
              onClick={() => removeMaPeriod(value)}
              className="opacity-70 transition hover:opacity-100"
              aria-label={`Remove MA ${value}`}
            >
              ×
            </button>
          </span>
        ))}

        <input
          type="number"
          min={1}
          inputMode="numeric"
          value={maInput}
          placeholder="+ MA"
          onChange={(event) => setMaInput(event.currentTarget.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              addMaPeriod();
            }
          }}
          className="h-7 w-16 rounded-lg border-none bg-[#2C2C2E] px-2 text-center text-xs text-white outline-none transition focus:outline focus:outline-1 focus:outline-[#0A84FF]"
        />
      </div>
    </div>
  );
}

function KLinePanelContent({ stockId, startDate, endDate, signalDate }: Props) {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-black">
      <ChartControls />
      <CandlestickChart
        stockId={stockId}
        startDate={startDate}
        endDate={endDate}
        signalDate={signalDate}
      />
    </div>
  );
}

export function KLinePanel({ stockId, startDate, endDate, signalDate }: Props) {
  return (
    <ChartControlsProvider>
      <KLinePanelContent
        stockId={stockId}
        startDate={startDate}
        endDate={endDate}
        signalDate={signalDate}
      />
    </ChartControlsProvider>
  );
}

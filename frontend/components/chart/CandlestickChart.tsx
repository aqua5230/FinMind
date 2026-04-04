"use client";

import { dispose, init, registerLocale, type KLineData, type Period as ChartPeriod } from "klinecharts";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/api";
import type { PriceResponse, StockBar } from "@/lib/types";

type Props = {
  stockId: string;
  startDate: string;
  endDate: string;
  chartType?: ChartType;
};

export type PeriodKey = "D" | "W" | "M";
export type ChartType = "candle_solid" | "candle_stroke";
export type IndicatorKey = "BOLL" | "MACD" | "RSI";

type ChartControlsState = {
  period: PeriodKey;
  setPeriod: (period: PeriodKey) => void;
  chartType: ChartType;
  setChartType: (chartType: ChartType) => void;
  maPeriods: number[];
  setMaPeriods: React.Dispatch<React.SetStateAction<number[]>>;
  maInput: string;
  setMaInput: (value: string) => void;
  activeIndicators: IndicatorKey[];
  setActiveIndicators: React.Dispatch<React.SetStateAction<IndicatorKey[]>>;
};

type ChartInstance = NonNullable<ReturnType<typeof init>>;

const DEFAULT_MA_PERIODS = [5, 20];
const DEFAULT_ACTIVE_INDICATORS: IndicatorKey[] = [];
const MA_COLORS = ["#F59E0B", "#34D399", "#60A5FA", "#F472B6", "#F87171", "#A78BFA"];
const CHART_LOCALE = "zh-TW";
const INDICATOR_PANES: Record<IndicatorKey, { id: string; height?: number }> = {
  BOLL: { id: "candle_pane" },
  MACD: { id: "macd_pane", height: 100 },
  RSI: { id: "rsi_pane", height: 100 },
};
const INDICATOR_PRECISIONS: Partial<Record<IndicatorKey, number>> = {
  MACD: 2,
  RSI: 2,
};

const PERIOD_MAP: Record<PeriodKey, ChartPeriod> = {
  D: { type: "day", span: 1 },
  W: { type: "week", span: 1 },
  M: { type: "month", span: 1 },
};

registerLocale(CHART_LOCALE, {
  time: "時間: ",
  open: "開: ",
  high: "高: ",
  low: "低: ",
  close: "收: ",
  volume: "量: ",
  turnover: "成交額: ",
  change: "漲跌幅: ",
  second: "秒",
  minute: "分",
  hour: "時",
  day: "日",
  week: "週",
  month: "月",
  year: "年",
});

const ChartControlsContext = createContext<ChartControlsState | null>(null);

export function ChartControlsProvider({ children }: { children: React.ReactNode }) {
  const [period, setPeriod] = useState<PeriodKey>("D");
  const [chartType, setChartType] = useState<ChartType>("candle_solid");
  const [maPeriods, setMaPeriods] = useState<number[]>(DEFAULT_MA_PERIODS);
  const [maInput, setMaInput] = useState("");
  const [activeIndicators, setActiveIndicators] = useState<IndicatorKey[]>(DEFAULT_ACTIVE_INDICATORS);

  return (
    <ChartControlsContext.Provider
      value={{
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
      }}
    >
      {children}
    </ChartControlsContext.Provider>
  );
}

export function useChartControls() {
  const context = useContext(ChartControlsContext);

  if (context) {
    return context;
  }

  return {
    period: "D" as PeriodKey,
    setPeriod: () => undefined,
    chartType: "candle_solid" as ChartType,
    setChartType: () => undefined,
    maPeriods: DEFAULT_MA_PERIODS,
    setMaPeriods: () => undefined,
    maInput: "",
    setMaInput: () => undefined,
    activeIndicators: DEFAULT_ACTIVE_INDICATORS,
    setActiveIndicators: () => undefined,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isBar(value: unknown): value is StockBar {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.date === "string" &&
    typeof value.open === "number" &&
    typeof value.high === "number" &&
    typeof value.low === "number" &&
    typeof value.close === "number" &&
    typeof value.volume === "number"
  );
}

function isPriceResponse(value: unknown): value is PriceResponse {
  if (!isRecord(value) || typeof value.stock_id !== "string" || !Array.isArray(value.prices)) {
    return false;
  }

  return value.prices.every(isBar);
}

function parseDateParts(date: string): { year: number; month: number; day: number } {
  const matched = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!matched) {
    throw new Error(`Invalid date: ${date}`);
  }

  const [, year, month, day] = matched;
  return {
    year: Number(year),
    month: Number(month),
    day: Number(day),
  };
}

function toUtcTimestamp(date: string): number {
  const { year, month, day } = parseDateParts(date);
  return Date.UTC(year, month - 1, day);
}

function sortBars(bars: StockBar[]): StockBar[] {
  return [...bars].sort((left, right) => left.date.localeCompare(right.date));
}

function aggregateBars(bars: StockBar[], period: PeriodKey): StockBar[] {
  if (period === "D") {
    return bars;
  }

  const grouped = new Map<string, StockBar>();

  for (const bar of bars) {
    const key = period === "W" ? getWeekKey(bar.date) : getMonthKey(bar.date);
    const existing = grouped.get(key);

    if (!existing) {
      grouped.set(key, { ...bar, date: period === "W" ? key : `${key}-01` });
      continue;
    }

    existing.high = Math.max(existing.high, bar.high);
    existing.low = Math.min(existing.low, bar.low);
    existing.close = bar.close;
    existing.volume += bar.volume;
  }

  return Array.from(grouped.values()).sort((left, right) => left.date.localeCompare(right.date));
}

function getWeekKey(date: string): string {
  const { year, month, day } = parseDateParts(date);
  const utcDate = new Date(Date.UTC(year, month - 1, day));
  const weekday = utcDate.getUTCDay();
  const diffToMonday = weekday === 0 ? -6 : 1 - weekday;
  utcDate.setUTCDate(utcDate.getUTCDate() + diffToMonday);
  return utcDate.toISOString().slice(0, 10);
}

function getMonthKey(date: string): string {
  return date.slice(0, 7);
}

function toKLineData(bars: StockBar[]): KLineData[] {
  return bars.map((bar) => ({
    timestamp: toUtcTimestamp(bar.date),
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
  }));
}

function getMaStyles(periods: number[]) {
  return {
    lines: periods.map((_, index) => ({
      color: MA_COLORS[index % MA_COLORS.length],
      size: 1,
      style: "solid" as const,
      dashedValue: [],
      smooth: false,
    })),
  };
}

export function normalizeMaPeriod(value: string): number | null {
  const parsed = Number(value.trim());
  if (!Number.isInteger(parsed) || parsed < 1) {
    return null;
  }
  return parsed;
}

export function CandlestickChart({
  stockId,
  startDate,
  endDate,
  chartType: initialChartType = "candle_solid",
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ChartInstance | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const chartDataRef = useRef<KLineData[]>([]);
  const { period, chartType = initialChartType, maPeriods, activeIndicators } = useChartControls();

  const [bars, setBars] = useState<StockBar[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const chart = init(container, {
      locale: CHART_LOCALE,
      timezone: "Asia/Taipei",
      formatter: {
        formatDate: ({ timestamp }) => {
          const date = new Date(timestamp);
          const y = date.getUTCFullYear();
          const m = String(date.getUTCMonth() + 1).padStart(2, "0");
          const d = String(date.getUTCDate()).padStart(2, "0");
          return `${y}-${m}-${d}`;
        },
      },
      styles: {
        grid: {
          horizontal: { color: "#2C2C2E", size: 1 },
          vertical: { show: false },
        },
        candle: {
          type: chartType,
          bar: {
            upColor: "#FF453A",
            downColor: "#30D158",
            noChangeColor: "#8E8E93",
            compareRule: "current_open",
            upBorderColor: "#FF453A",
            downBorderColor: "#30D158",
            noChangeBorderColor: "#8E8E93",
            upWickColor: "#FF453A",
            downWickColor: "#30D158",
            noChangeWickColor: "#8E8E93",
          },
          priceMark: {
            last: {
              upColor: "#FF453A",
              downColor: "#30D158",
              noChangeColor: "#8E8E93",
              compareRule: "current_open",
              line: { show: false },
            },
          },
          tooltip: {
            title: {
              show: false,
            },
          },
        },
        xAxis: {
          axisLine: { color: "#3A3A3C" },
          tickLine: { color: "#3A3A3C" },
          tickText: { color: "#6B6B70", size: 11 },
        },
        yAxis: {
          axisLine: { color: "#3A3A3C" },
          tickLine: { color: "#3A3A3C" },
          tickText: { color: "#6B6B70", size: 11 },
        },
        crosshair: {
          horizontal: {
            line: { color: "#545458" },
            text: { backgroundColor: "#2C2C2E", color: "#FFFFFF" },
          },
          vertical: {
            line: { color: "#545458" },
            text: { backgroundColor: "#2C2C2E", color: "#FFFFFF" },
          },
        },
        separator: {
          color: "#3A3A3C",
          activeBackgroundColor: "#2C2C2E",
        },
      },
    } as Parameters<typeof init>[1]);

    if (!chart) {
      return;
    }

    chart.setSymbol({ ticker: stockId, pricePrecision: 2, volumePrecision: 0 });
    chart.createIndicator("MA", true, { id: "candle_pane" });
    chart.createIndicator("VOL", false, { id: "vol_pane", height: 120 });
    chart.overrideIndicator({
      name: "VOL",
      shortName: "量",
      tooltip: {
        legendVisible: true,
      },
    } as Parameters<typeof chart.overrideIndicator>[0]);
    chart.setDataLoader({
      getBars: ({ callback }) => {
        callback(chartDataRef.current, { backward: false, forward: false });
      },
    });

    chartRef.current = chart;
    resizeObserverRef.current = new ResizeObserver(() => {
      chart.resize();
    });
    resizeObserverRef.current.observe(container);
    chart.resize();

    return () => {
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      chartRef.current = null;
      dispose(container);
    };
  }, [stockId]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) {
      return;
    }

    chart.setStyles({
      candle: { type: chartType },
    });
  }, [chartType]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadPrices() {
      setIsLoading(true);
      setError(null);

      try {
        const query = new URLSearchParams({
          start_date: startDate,
          end_date: endDate,
        });

        const response = await fetch(`${API_URL}/api/price/${stockId}?${query.toString()}`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("Failed to fetch prices");
        }

        const payload: unknown = await response.json();
        if (!isPriceResponse(payload)) {
          throw new Error("Invalid payload");
        }

        setBars(sortBars(payload.prices));
      } catch {
        if (controller.signal.aborted) {
          return;
        }

        setBars([]);
        setError("無法載入價格資料");
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void loadPrices();

    return () => controller.abort();
  }, [stockId, startDate, endDate]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) {
      return;
    }

    const nextData = toKLineData(aggregateBars(sortBars(bars), period));
    chartDataRef.current = nextData;

    chart.setPeriod(PERIOD_MAP[period]);
    chart.overrideIndicator({
      name: "MA",
      shortName: "均線",
      paneId: "candle_pane",
      calcParams: maPeriods,
      styles: getMaStyles(maPeriods),
    });
    chart.resetData();
    chart.scrollToRealTime();
  }, [bars, maPeriods, period]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) {
      return;
    }

    const activeIndicatorSet = new Set(activeIndicators);

    (Object.entries(INDICATOR_PANES) as Array<[IndicatorKey, (typeof INDICATOR_PANES)[IndicatorKey]]>).forEach(
      ([indicator, paneOptions]) => {
        const isActive = activeIndicatorSet.has(indicator);
        const exists = chart.getIndicators({ paneId: paneOptions.id, name: indicator }).length > 0;

        if (isActive && !exists) {
          chart.createIndicator(indicator, false, paneOptions);

          const precision = INDICATOR_PRECISIONS[indicator];
          if (precision !== undefined) {
            chart.overrideIndicator({
              name: indicator,
              calcParams: [],
              precision,
            } as Parameters<typeof chart.overrideIndicator>[0]);
          }

          return;
        }

        if (!isActive && exists) {
          if (paneOptions.id === "candle_pane") {
            chart.removeIndicator({ paneId: paneOptions.id, name: indicator });
            return;
          }

          chart.removeIndicator({ paneId: paneOptions.id });
        }
      },
    );
  }, [activeIndicators, stockId]);

  return (
    <div className="relative overflow-hidden bg-black" style={{ height: "calc(100vh - 160px)" }}>
      <div ref={containerRef} className="h-full w-full" />

      {isLoading ? <div className="absolute inset-0 animate-pulse bg-[#1C1C1E]" /> : null}

      {!isLoading && error ? (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-[#6B6B70]">
          {error}
        </div>
      ) : null}
    </div>
  );
}

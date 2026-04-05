"use client";

import { dispose, init, registerLocale, type KLineData, type Period as ChartPeriod } from "klinecharts";
import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useStockData } from "@/hooks/useStockData";
import type { StockBar } from "@/lib/types";

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
const MA_COLORS = ["#C4956A", "#7FA9A0", "#9BABB8", "#B69DB8", "#8FAF8F", "#BF9D9D"];
const CHART_LOCALE = "zh-TW";
const UP_COLOR = "#FF453A";
const DOWN_COLOR = "#30D158";
const NO_CHANGE_COLOR = "#8E8E93";
const INDICATOR_PANES: Record<IndicatorKey, { id: string; height?: number }> = {
  BOLL: { id: "candle_pane" },
  MACD: { id: "macd_pane", height: 80 },
  RSI: { id: "rsi_pane", height: 80 },
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

function getCandleStyles(chartType: ChartType) {
  return {
    candle: {
      type: chartType,
      bar: {
        upColor: UP_COLOR,
        downColor: DOWN_COLOR,
        noChangeColor: NO_CHANGE_COLOR,
        compareRule: "current_open" as const,
        upBorderColor: UP_COLOR,
        downBorderColor: DOWN_COLOR,
        noChangeBorderColor: NO_CHANGE_COLOR,
        upWickColor: UP_COLOR,
        downWickColor: DOWN_COLOR,
        noChangeWickColor: NO_CHANGE_COLOR,
      },
      priceMark: {
        last: {
          upColor: UP_COLOR,
          downColor: DOWN_COLOR,
          noChangeColor: NO_CHANGE_COLOR,
          line: { show: false },
        },
      },
      tooltip: {
        showRule: "follow_cross" as const,
        title: {
          show: false,
        },
      },
    },
  };
}

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

type ChartWithDataApply = ChartInstance & {
  applyNewData?: (data: KLineData[]) => void;
};

function replaceChartData(chart: ChartInstance, data: KLineData[]) {
  const nextChart = chart as ChartWithDataApply;

  if (typeof nextChart.applyNewData === "function") {
    nextChart.applyNewData(data);
    return;
  }

  chart.resetData();
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
  const periodRef = useRef<PeriodKey>("D");
  const chartDataRef = useRef<KLineData[]>([]);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const { period, chartType = initialChartType, maPeriods, activeIndicators } = useChartControls();
  const { data: bars, loading: isLoading, error } = useStockData(stockId, startDate, endDate);
  const nextData = useMemo(() => toKLineData(aggregateBars(sortBars(bars), period)), [bars, period]);

  useEffect(() => {
    chartDataRef.current = nextData;
  }, [nextData]);
  useEffect(() => { periodRef.current = period; }, [period]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || isLoading) {
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
        ...getCandleStyles(initialChartType),
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
    chart.setPeriod(PERIOD_MAP[periodRef.current]);
    chart.setDataLoader({
      getBars: ({ callback }) => {
        callback(chartDataRef.current, { backward: false, forward: false });
      },
    });
    chart.createIndicator("MA", true, { id: "candle_pane" });
    chart.createIndicator("VOL", false, { id: "vol_pane", height: 80 });
    chart.setPaneOptions({ id: "candle_pane", minHeight: 250 });
    chart.overrideIndicator({
      name: "VOL",
      shortName: "量",
      tooltip: {
        legendVisible: true,
      },
    } as Parameters<typeof chart.overrideIndicator>[0]);

    chartRef.current = chart;
    resizeObserverRef.current = new ResizeObserver(() => {
      chart.resize();
    });
    resizeObserverRef.current.observe(container);
    chart.resize();
    chart.setPaneOptions({ id: "vol_pane", height: 80 });

    if (chartDataRef.current.length > 0) {
      replaceChartData(chart, chartDataRef.current);
      chart.scrollToRealTime();
    }

    return () => {
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      chartRef.current = null;
      dispose(container);
    };
  }, [initialChartType, isLoading, stockId]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) {
      return;
    }

    try {
      chart.setStyles(getCandleStyles(chartType));
    } catch (error) {
      console.error("Failed to switch candle chart type", error);
    }
  }, [chartType]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) {
      return;
    }

    chart.setPeriod(PERIOD_MAP[period]);
    chart.overrideIndicator({
      name: "MA",
      shortName: "均線",
      paneId: "candle_pane",
      calcParams: maPeriods,
      styles: getMaStyles(maPeriods),
    });
    chartDataRef.current = nextData;
    replaceChartData(chart, nextData);
    chart.scrollToRealTime();
  }, [maPeriods, nextData, period]);

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
          chart.setPaneOptions({ id: paneOptions.id, height: paneOptions.height ?? 80 });

          const precision = INDICATOR_PRECISIONS[indicator];
          if (precision !== undefined) {
            chart.overrideIndicator({
              name: indicator,
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
  }, [activeIndicators, isLoading, stockId]);

  return (
    <div className="relative overflow-hidden bg-black" style={{ height: "calc(100vh - 160px)" }}>
      <div ref={containerRef} className="h-full w-full" />

      {isLoading ? (
        <div className="absolute inset-0 bg-black">
          <div className="pointer-events-none absolute inset-0">
            {[...Array(5)].map((_, index) => (
              <div
                key={`grid-line-${index}`}
                className="absolute left-0 right-0 border-t border-dashed border-white/10"
                style={{ top: `${((index + 1) / 6) * 100}%` }}
              />
            ))}
          </div>

          <div className="pointer-events-none absolute inset-x-4 bottom-6 flex h-3/5 items-end justify-between gap-1">
            {[
              "h-[18%]",
              "h-[34%]",
              "h-[26%]",
              "h-[48%]",
              "h-[22%]",
              "h-[56%]",
              "h-[30%]",
              "h-[44%]",
              "h-[20%]",
              "h-[62%]",
              "h-[28%]",
              "h-[52%]",
              "h-[24%]",
              "h-[40%]",
              "h-[16%]",
              "h-[58%]",
              "h-[36%]",
              "h-[46%]",
              "h-[32%]",
              "h-[54%]",
            ].map((heightClass, index) => (
              <div key={`skeleton-bar-${index}`} className="flex h-full flex-1 items-end justify-center">
                <div className={`w-full max-w-2 rounded-sm bg-white/12 animate-pulse ${heightClass}`} />
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {!isLoading && error ? (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-[#6B6B70]">
          {error}
        </div>
      ) : null}
    </div>
  );
}

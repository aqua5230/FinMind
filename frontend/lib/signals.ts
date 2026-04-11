import type { KLineData } from "klinecharts";

export type TradeSignalType = "long" | "short";

export type TradeSignal = {
  type: TradeSignalType;
  timestamp: number;
  value: number;
};

const BOLL_PERIOD = 20;
const BOLL_MULTIPLIER = 2;
const RSI_PERIOD = 14;
const VOLUME_MA_PERIOD = 10;
const MACD_FAST = 12;
const MACD_SLOW = 26;
const MACD_SIGNAL = 9;

type BollPoint = {
  upper: number | null;
  lower: number | null;
};

type MacdPoint = {
  histogram: number | null;
};

function calculateBoll(candles: KLineData[]): BollPoint[] {
  let sum = 0;
  return candles.map((candle, index) => {
    sum += candle.close;

    if (index < BOLL_PERIOD - 1) {
      return { upper: null, lower: null };
    }

    const start = index - BOLL_PERIOD + 1;
    const window = candles.slice(start, index + 1);
    const middle = sum / BOLL_PERIOD;
    const variance = window.reduce((total, item) => total + (item.close - middle) ** 2, 0) / BOLL_PERIOD;
    const deviation = Math.sqrt(variance);

    sum -= candles[start].close;

    return {
      upper: middle + BOLL_MULTIPLIER * deviation,
      lower: middle - BOLL_MULTIPLIER * deviation,
    };
  });
}

function calculateRsi(candles: KLineData[]): Array<number | null> {
  let gainSum = 0;
  let lossSum = 0;

  return candles.map((candle, index) => {
    const previousClose = candles[index - 1]?.close ?? candle.close;
    const change = candle.close - previousClose;

    if (change > 0) {
      gainSum += change;
    } else {
      lossSum += Math.abs(change);
    }

    if (index < RSI_PERIOD) {
      return null;
    }

    const rsi = lossSum === 0 ? 100 : 100 - 100 / (1 + gainSum / lossSum);
    const oldClose = candles[index - RSI_PERIOD + 1].close;
    const oldPreviousClose = candles[index - RSI_PERIOD]?.close ?? oldClose;
    const oldChange = oldClose - oldPreviousClose;

    if (oldChange > 0) {
      gainSum -= oldChange;
    } else {
      lossSum -= Math.abs(oldChange);
    }

    return rsi;
  });
}

function calculateMacd(candles: KLineData[]): MacdPoint[] {
  let closeSum = 0;
  let fastEma = 0;
  let slowEma = 0;
  let difSum = 0;
  let dea = 0;
  const maxPeriod = Math.max(MACD_FAST, MACD_SLOW);

  return candles.map((candle, index) => {
    closeSum += candle.close;

    if (index >= MACD_FAST - 1) {
      fastEma =
        index === MACD_FAST - 1
          ? closeSum / MACD_FAST
          : (2 * candle.close + (MACD_FAST - 1) * fastEma) / (MACD_FAST + 1);
    }

    if (index >= MACD_SLOW - 1) {
      slowEma =
        index === MACD_SLOW - 1
          ? closeSum / MACD_SLOW
          : (2 * candle.close + (MACD_SLOW - 1) * slowEma) / (MACD_SLOW + 1);
    }

    if (index < maxPeriod - 1) {
      return { histogram: null };
    }

    const dif = fastEma - slowEma;
    difSum += dif;

    if (index < maxPeriod + MACD_SIGNAL - 2) {
      return { histogram: null };
    }

    dea =
      index === maxPeriod + MACD_SIGNAL - 2
        ? difSum / MACD_SIGNAL
        : (2 * dif + (MACD_SIGNAL - 1) * dea) / (MACD_SIGNAL + 1);

    return { histogram: dif - dea };
  });
}

function calculateVolumeMa(candles: KLineData[]): Array<number | null> {
  let sum = 0;

  return candles.map((candle, index) => {
    sum += candle.volume as number;

    if (index < VOLUME_MA_PERIOD - 1) {
      return null;
    }

    const average = sum / VOLUME_MA_PERIOD;
    sum -= candles[index - VOLUME_MA_PERIOD + 1].volume as number;

    return average;
  });
}

function isNumber(value: number | null): value is number {
  return value !== null && Number.isFinite(value);
}

export function calculateTradeSignals(candles: KLineData[]): TradeSignal[] {
  const rsi = calculateRsi(candles);
  const signals: TradeSignal[] = [];

  for (let index = 1; index < candles.length; index += 1) {
    const candle = candles[index];
    const currentRsi = rsi[index];
    const startIdx = Math.max(0, index - 20);
    const peak20 = Math.max(...candles.slice(startIdx, index).map((c) => c.close));

    if (
      isNumber(currentRsi) &&
      currentRsi < 30 &&
      candle.close <= peak20 * 0.8
    ) {
      signals.push({
        type: "long",
        timestamp: candle.timestamp,
        value: candle.low * 0.995,
      });
    }
  }

  return signals;
}

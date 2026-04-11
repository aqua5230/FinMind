import type { KLineData } from "klinecharts";

export type TradeSignalType = "long" | "short";

export type TradeSignal = {
  type: TradeSignalType;
  timestamp: number;
  value: number;
};

const RSI_PERIOD = 14;

function calculateRsi(candles: KLineData[]): Array<number | null> {
  const result: Array<number | null> = new Array(candles.length).fill(null);
  if (candles.length <= RSI_PERIOD) return result;

  // 初始化：前 RSI_PERIOD 個 bar 的平均漲跌幅（Wilder's 標準法）
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i <= RSI_PERIOD; i++) {
    const change = candles[i].close - candles[i - 1].close;
    if (change > 0) avgGain += change;
    else avgLoss += Math.abs(change);
  }
  avgGain /= RSI_PERIOD;
  avgLoss /= RSI_PERIOD;
  result[RSI_PERIOD] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);

  // 後續：Wilder's EMA 平滑
  for (let i = RSI_PERIOD + 1; i < candles.length; i++) {
    const change = candles[i].close - candles[i - 1].close;
    const gain = Math.max(change, 0);
    const loss = Math.max(-change, 0);
    avgGain = (avgGain * (RSI_PERIOD - 1) + gain) / RSI_PERIOD;
    avgLoss = (avgLoss * (RSI_PERIOD - 1) + loss) / RSI_PERIOD;
    result[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }

  return result;
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
// 1775926263

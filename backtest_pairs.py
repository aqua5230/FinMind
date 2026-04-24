"""
Pairs trading backtest for local TW stock parquet cache.

The signal calculation mirrors stock_report/api/pair_scan.py:
- close-to-close returns
- correlation filter
- return-spread z-score using the most recent 5 trading days against history
"""
from __future__ import annotations

import math
import os
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import matplotlib

os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="mplconfig-"))
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PRICE_CACHE_DIR = Path("data/price_cache")
TRADES_OUTPUT = Path("pairs_backtest_trades.csv")
EQUITY_OUTPUT = Path("pairs_backtest_equity.png")

START_DATE = "2020-01-01"
END_DATE = "2025-12-31"
SPLIT_DATE = "2023-01-01"
LOOKBACK = 90
RECENT_DAYS = 5
SCAN_INTERVAL_DAYS = 5

INITIAL_CAPITAL = 1_000_000.0
POSITION_PCT = 0.10
MAX_POSITIONS = 10

CORR_THRESHOLD = 0.75
ENTRY_Z = 1.5
EXIT_Z = 0.3
MAX_HOLD_DAYS = 15
STOP_LOSS_PCT = -0.05
MIN_DAILY_TURNOVER = 5_000_000.0
MIN_OBSERVATIONS = 60
RISK_FREE_RATE = 0.015
TRADING_DAYS = 252

BUY_FEE = 0.001425
SELL_FEE = 0.001425
SELL_TAX = 0.003


Direction = Literal["SHORT_A_LONG_B", "SHORT_B_LONG_A"]


@dataclass
class Position:
    pair_key: tuple[str, str]
    stock_a: str
    stock_b: str
    direction: Direction
    entry_date: pd.Timestamp
    entry_dev: float
    notional: float
    leg_notional: float
    entry_long_price: float
    entry_short_price: float
    long_stock: str
    short_stock: str
    entry_cost: float


def _first_existing_column(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lower_map = {str(c).lower(): str(c) for c in df.columns}
    for name in names:
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None


def load_all_prices() -> dict[str, pd.DataFrame]:
    """Load all parquet files, return {stock_id: df with DatetimeIndex}."""
    result: dict[str, pd.DataFrame] = {}
    for f in sorted(PRICE_CACHE_DIR.glob("*.parquet")):
        stock_id = f.stem.split("_")[0]
        try:
            df = pd.read_parquet(f)
        except Exception as exc:
            print(f"Skip {f.name}: read failed ({exc})")
            continue

        date_col = _first_existing_column(df, ("Date", "date"))
        if date_col is not None:
            df = df.set_index(date_col)

        close_col = _first_existing_column(df, ("Close", "close", "Adj Close", "adj close"))
        volume_col = _first_existing_column(df, ("Volume", "volume"))
        if close_col is None or volume_col is None:
            continue

        out = pd.DataFrame(index=pd.to_datetime(df.index, errors="coerce"))
        out["close"] = pd.to_numeric(df[close_col], errors="coerce")
        out["volume"] = pd.to_numeric(df[volume_col], errors="coerce")
        out = out[~out.index.isna()]
        out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=["close", "volume"])
        out = out[out["close"] > 0].sort_index()
        out = out[~out.index.duplicated(keep="last")]
        if len(out) >= LOOKBACK:
            result[stock_id] = out
    return result


def build_pivots(prices: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    closes = []
    volumes = []
    for stock_id, df in prices.items():
        close = df["close"].rename(stock_id)
        volume = df["volume"].rename(stock_id)
        closes.append(close)
        volumes.append(volume)

    close_pivot = pd.concat(closes, axis=1).sort_index()
    volume_pivot = pd.concat(volumes, axis=1).sort_index()
    close_pivot = close_pivot.loc[close_pivot.index <= pd.Timestamp(END_DATE)]
    volume_pivot = volume_pivot.reindex(close_pivot.index)
    return close_pivot, volume_pivot


def pair_key(stock_a: str, stock_b: str) -> tuple[str, str]:
    return tuple(sorted((stock_a, stock_b)))


def compute_deviation(returns: pd.DataFrame, stock_a: str, stock_b: str) -> float:
    spread = (returns[stock_a] - returns[stock_b]).dropna()
    if len(spread) < RECENT_DAYS + 10:
        return float("nan")

    hist = spread.iloc[:-RECENT_DAYS]
    hist_std = hist.std()
    if not np.isfinite(hist_std) or hist_std <= 0:
        return float("nan")

    hist_mean = hist.mean()
    recent_mean = spread.iloc[-RECENT_DAYS:].mean()
    deviation = (recent_mean - hist_mean) / hist_std
    return float(deviation) if np.isfinite(deviation) else float("nan")


def scan_pairs(
    close_window: pd.DataFrame,
    volume_window: pd.DataFrame,
    active_pairs: set[tuple[str, str]],
) -> list[dict[str, float | str]]:
    close_window = close_window.dropna(thresh=MIN_OBSERVATIONS, axis=1).ffill()
    if close_window.shape[1] < 2:
        return []

    volume_window = volume_window.reindex(index=close_window.index, columns=close_window.columns)
    turnover = close_window * volume_window
    avg_turnover = turnover.mean(skipna=True)
    liquid = avg_turnover[avg_turnover >= MIN_DAILY_TURNOVER].index
    close_window = close_window.loc[:, liquid]
    if close_window.shape[1] < 2:
        return []

    returns = close_window.pct_change().dropna(how="all")
    returns = returns.dropna(thresh=MIN_OBSERVATIONS - 1, axis=1)
    if returns.shape[1] < 2:
        return []

    corr_matrix = returns.corr()
    columns = np.asarray(corr_matrix.columns)
    corr_values = corr_matrix.to_numpy(dtype=float)
    upper_i, upper_j = np.triu_indices_from(corr_values, k=1)
    selected = np.where(corr_values[upper_i, upper_j] >= CORR_THRESHOLD)[0]

    candidates: list[dict[str, float | str]] = []
    for idx in selected:
        stock_a = str(columns[upper_i[idx]])
        stock_b = str(columns[upper_j[idx]])
        key = pair_key(stock_a, stock_b)
        if key in active_pairs:
            continue

        deviation = compute_deviation(returns, stock_a, stock_b)
        if not np.isfinite(deviation) or abs(deviation) < ENTRY_Z:
            continue

        candidates.append(
            {
                "stock_a": stock_a,
                "stock_b": stock_b,
                "correlation": float(corr_values[upper_i[idx], upper_j[idx]]),
                "deviation": deviation,
            }
        )

    candidates.sort(key=lambda row: abs(float(row["deviation"])), reverse=True)
    return candidates


def mark_pair_pnl_pct(position: Position, prices: pd.Series) -> float:
    long_price = float(prices.get(position.long_stock, np.nan))
    short_price = float(prices.get(position.short_stock, np.nan))
    if not np.isfinite(long_price) or not np.isfinite(short_price):
        return 0.0

    long_pnl = (long_price / position.entry_long_price - 1.0) * position.leg_notional
    short_pnl = (position.entry_short_price / short_price - 1.0) * position.leg_notional
    return (long_pnl + short_pnl) / position.notional


def close_position(
    position: Position,
    exit_date: pd.Timestamp,
    exit_dev: float,
    exit_reason: str,
    prices: pd.Series,
) -> tuple[dict[str, object], float]:
    long_exit = float(prices[position.long_stock])
    short_exit = float(prices[position.short_stock])

    long_gross = (long_exit / position.entry_long_price - 1.0) * position.leg_notional
    short_gross = (position.entry_short_price / short_exit - 1.0) * position.leg_notional
    # Exit: long leg sells (SELL_FEE+SELL_TAX), short leg covers/buys (BUY_FEE).
    exit_cost = position.leg_notional * (SELL_FEE + SELL_TAX) + position.leg_notional * BUY_FEE
    net_pnl = long_gross + short_gross - position.entry_cost - exit_cost
    pnl_pct = net_pnl / position.notional
    hold_days = int((exit_date - position.entry_date).days)

    trade = {
        "pair": f"{position.stock_a}-{position.stock_b}",
        "direction": position.direction,
        "entry_date": position.entry_date.date().isoformat(),
        "exit_date": exit_date.date().isoformat(),
        "hold_days": hold_days,
        "entry_dev": round(position.entry_dev, 4),
        "exit_dev": round(float(exit_dev), 4) if np.isfinite(exit_dev) else np.nan,
        "pnl_pct": round(pnl_pct * 100.0, 4),
        "exit_reason": exit_reason,
    }
    return trade, net_pnl


def open_position(candidate: dict[str, float | str], date: pd.Timestamp, prices: pd.Series, equity: float) -> Position | None:
    stock_a = str(candidate["stock_a"])
    stock_b = str(candidate["stock_b"])
    deviation = float(candidate["deviation"])

    price_a = float(prices.get(stock_a, np.nan))
    price_b = float(prices.get(stock_b, np.nan))
    if not np.isfinite(price_a) or not np.isfinite(price_b) or price_a <= 0 or price_b <= 0:
        return None

    notional = equity * POSITION_PCT
    leg_notional = notional / 2.0
    direction: Direction
    if deviation > 0:
        direction = "SHORT_A_LONG_B"
        short_stock, long_stock = stock_a, stock_b
        entry_short_price, entry_long_price = price_a, price_b
    else:
        direction = "SHORT_B_LONG_A"
        short_stock, long_stock = stock_b, stock_a
        entry_short_price, entry_long_price = price_b, price_a

    # Entry: short leg sells (SELL_FEE+SELL_TAX), long leg buys (BUY_FEE).
    # notional itself is not deducted from cash — long/short legs are market-neutral and net to ~zero.
    entry_cost = leg_notional * (SELL_FEE + SELL_TAX) + leg_notional * BUY_FEE
    return Position(
        pair_key=pair_key(stock_a, stock_b),
        stock_a=stock_a,
        stock_b=stock_b,
        direction=direction,
        entry_date=date,
        entry_dev=deviation,
        notional=notional,
        leg_notional=leg_notional,
        entry_long_price=entry_long_price,
        entry_short_price=entry_short_price,
        long_stock=long_stock,
        short_stock=short_stock,
        entry_cost=entry_cost,
    )


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return float(drawdown.min())


def profit_factor(pnls: pd.Series) -> float:
    gains = pnls[pnls > 0].sum()
    losses = pnls[pnls < 0].sum()
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / abs(losses))


def annual_return(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    days = max((equity.index[-1] - equity.index[0]).days, 1)
    return float((1.0 + total_return) ** (365.25 / days) - 1.0)


def sharpe_ratio(equity: pd.Series) -> float:
    daily = equity.pct_change().dropna()
    if daily.empty or daily.std() == 0:
        return 0.0
    excess_daily = daily - RISK_FREE_RATE / TRADING_DAYS
    return float(math.sqrt(TRADING_DAYS) * excess_daily.mean() / daily.std())


def summarize_period(name: str, equity: pd.Series, trades: pd.DataFrame) -> dict[str, float | int | str]:
    if equity.empty:
        return {
            "period": name,
            "trades": 0,
            "win_rate": 0.0,
            "total_return": 0.0,
            "annual_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
            "avg_hold_days": 0.0,
        }

    pnl_pct = trades["pnl_pct"] / 100.0 if not trades.empty else pd.Series(dtype=float)
    return {
        "period": name,
        "trades": int(len(trades)),
        "win_rate": float((pnl_pct > 0).mean() * 100.0) if len(pnl_pct) else 0.0,
        "total_return": float((equity.iloc[-1] / equity.iloc[0] - 1.0) * 100.0),
        "annual_return": annual_return(equity) * 100.0,
        "sharpe": sharpe_ratio(equity),
        "max_drawdown": max_drawdown(equity) * 100.0,
        "profit_factor": profit_factor(pnl_pct),
        "avg_hold_days": float(trades["hold_days"].mean()) if not trades.empty else 0.0,
    }


def print_summary(summary: dict[str, float | int | str]) -> None:
    pf = summary["profit_factor"]
    pf_text = "inf" if math.isinf(float(pf)) else f"{float(pf):.2f}"
    print(f"\n=== {summary['period']} ===")
    print(f"總交易筆數       : {summary['trades']}")
    print(f"勝率             : {float(summary['win_rate']):.2f}%")
    print(f"總報酬           : {float(summary['total_return']):.2f}%")
    print(f"年化報酬         : {float(summary['annual_return']):.2f}%")
    print(f"Sharpe ratio     : {float(summary['sharpe']):.2f}")
    print(f"Max Drawdown     : {float(summary['max_drawdown']):.2f}%")
    print(f"Profit Factor    : {pf_text}")
    print(f"平均持倉天數     : {float(summary['avg_hold_days']):.2f}")


def plot_equity(equity: pd.Series) -> None:
    split = pd.Timestamp(SPLIT_DATE)
    fig, ax = plt.subplots(figsize=(12, 6))
    train = equity[equity.index < split]
    test = equity[equity.index >= split]
    if not train.empty:
        ax.plot(train.index, train.values, label="Train", color="#2f6fdd", linewidth=1.8)
    if not test.empty:
        ax.plot(test.index, test.values, label="Test", color="#d14b3f", linewidth=1.8)
    ax.axvline(split, color="#444444", linestyle="--", linewidth=1.0, label="Split")
    ax.set_title("Pairs Trading Backtest Equity Curve")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity (TWD)")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(EQUITY_OUTPUT, dpi=160)
    plt.close(fig)


def run_backtest(close_pivot: pd.DataFrame, volume_pivot: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    start_ts = pd.Timestamp(START_DATE)
    end_ts = pd.Timestamp(END_DATE)
    close_ffill = close_pivot.ffill()
    dates = close_ffill.loc[(close_ffill.index >= start_ts) & (close_ffill.index <= end_ts)].index

    # Pre-build position index for O(1) iloc slicing instead of O(n) loc[:date] each day.
    all_idx = close_ffill.index
    date_to_pos = {d: i for i, d in enumerate(all_idx)}

    cash = INITIAL_CAPITAL
    positions: list[Position] = []
    trades: list[dict[str, object]] = []
    equity_points: list[tuple[pd.Timestamp, float]] = []
    last_candidates: list[dict[str, float | str]] = []

    for step, date in enumerate(dates):
        prices = close_ffill.loc[date]
        pos = date_to_pos[date]
        hist_close = close_ffill.iloc[max(0, pos - LOOKBACK):pos + 1]
        hist_volume = volume_pivot.iloc[max(0, pos - LOOKBACK):pos + 1]
        returns = hist_close.dropna(thresh=MIN_OBSERVATIONS, axis=1).ffill().pct_change().dropna(how="all")

        remaining: list[Position] = []
        for position in positions:
            if not np.isfinite(prices.get(position.long_stock, np.nan)) or not np.isfinite(prices.get(position.short_stock, np.nan)):
                remaining.append(position)
                continue

            exit_dev = compute_deviation(returns, position.stock_a, position.stock_b)
            hold_days = int((date - position.entry_date).days)
            mark_pnl_pct = mark_pair_pnl_pct(position, prices)
            exit_reason = ""
            if np.isfinite(exit_dev) and abs(exit_dev) < EXIT_Z:
                exit_reason = "mean_reversion"
            elif hold_days >= MAX_HOLD_DAYS:
                exit_reason = "max_hold_days"
            elif mark_pnl_pct < STOP_LOSS_PCT:
                exit_reason = "stop_loss"

            if exit_reason:
                trade, net_pnl = close_position(position, date, exit_dev, exit_reason, prices)
                trades.append(trade)
                cash += net_pnl
            else:
                remaining.append(position)
        positions = remaining

        active_pairs = {p.pair_key for p in positions}
        if step % SCAN_INTERVAL_DAYS == 0:
            last_candidates = scan_pairs(hist_close, hist_volume, active_pairs)

        # Compute equity once before opening new positions (used to size notional).
        current_unrealized = sum(mark_pair_pnl_pct(p, prices) * p.notional for p in positions)
        equity = cash + current_unrealized

        for candidate in last_candidates:
            if len(positions) >= MAX_POSITIONS:
                break
            stock_a = str(candidate["stock_a"])
            stock_b = str(candidate["stock_b"])
            key = pair_key(stock_a, stock_b)
            if key in active_pairs:  # reuse set built above; update after append
                continue

            position = open_position(candidate, date, prices, equity)
            if position is None:
                continue

            positions.append(position)
            active_pairs.add(position.pair_key)
            cash -= position.entry_cost

        # Recompute unrealized after opening to include any new positions.
        current_unrealized = sum(mark_pair_pnl_pct(p, prices) * p.notional for p in positions)
        equity_points.append((date, cash + current_unrealized))

        if (step + 1) % 100 == 0:
            print(f"Processed {step + 1}/{len(dates)} trading days, trades={len(trades)}, open={len(positions)}")

    if positions and len(dates) > 0:
        final_date = dates[-1]
        prices = close_ffill.loc[final_date]
        final_pos = date_to_pos[final_date]
        final_hist = close_ffill.iloc[max(0, final_pos - LOOKBACK):final_pos + 1]
        # Apply same cleaning as main loop so deviation is computed consistently.
        final_returns = final_hist.dropna(thresh=MIN_OBSERVATIONS, axis=1).ffill().pct_change().dropna(how="all")
        for position in positions:
            exit_dev = compute_deviation(final_returns, position.stock_a, position.stock_b)
            if np.isfinite(prices.get(position.long_stock, np.nan)) and np.isfinite(prices.get(position.short_stock, np.nan)):
                trade, net_pnl = close_position(position, final_date, exit_dev, "end_of_backtest", prices)
                trades.append(trade)
                cash += net_pnl

    trades_df = pd.DataFrame(
        trades,
        columns=["pair", "direction", "entry_date", "exit_date", "hold_days", "entry_dev", "exit_dev", "pnl_pct", "exit_reason"],
    )
    equity_series = pd.Series(
        data=[v for _, v in equity_points],
        index=pd.DatetimeIndex([d for d, _ in equity_points], name="date"),
        name="equity",
    )
    return trades_df, equity_series


def main() -> None:
    try:
        print("Loading local parquet price cache...")
        prices = load_all_prices()
        if not prices:
            raise RuntimeError(f"No usable parquet files found under {PRICE_CACHE_DIR}")

        print(f"Loaded {len(prices)} stocks. Building price matrices...")
        close_pivot, volume_pivot = build_pivots(prices)
        print(f"Price matrix: {close_pivot.shape[0]} dates x {close_pivot.shape[1]} stocks")

        trades_df, equity = run_backtest(close_pivot, volume_pivot)
        if equity.empty:
            raise RuntimeError("No equity curve was generated")

        trades_df.to_csv(TRADES_OUTPUT, index=False)
        plot_equity(equity)

        split = pd.Timestamp(SPLIT_DATE)
        train_equity = equity[equity.index < split]
        test_equity = equity[equity.index >= split]
        trades_for_summary = trades_df.copy()
        if not trades_for_summary.empty:
            trades_for_summary["exit_date"] = pd.to_datetime(trades_for_summary["exit_date"])
        train_trades = trades_for_summary[trades_for_summary["exit_date"] < split] if not trades_for_summary.empty else trades_for_summary
        test_trades = trades_for_summary[trades_for_summary["exit_date"] >= split] if not trades_for_summary.empty else trades_for_summary

        print_summary(summarize_period("TRAIN 2020-01-01 to 2022-12-31", train_equity, train_trades))
        print_summary(summarize_period("TEST 2023-01-01 to 2025-12-31", test_equity, test_trades))
        print(f"\nSaved trades: {TRADES_OUTPUT}")
        print(f"Saved equity curve: {EQUITY_OUTPUT}")
    except Exception as exc:
        print(f"FAIL: {exc}")
        print("影響範圍: 建立配對交易回測輸出")
        print("建議: 檢查 data/price_cache parquet 欄位、套件安裝與輸出目錄權限")


if __name__ == "__main__":
    main()

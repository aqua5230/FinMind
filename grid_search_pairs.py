"""
Grid search for pairs trading strategy parameters.
Loads parquet cache once, then sweeps 27 parameter combinations.

Search space:
  ENTRY_Z      : [1.5, 2.0, 2.5]
  MAX_HOLD_DAYS: [15, 20, 30]
  STOP_LOSS_PCT: [-0.05, -0.08, -0.10]

Selects best combo by Train Sharpe, then validates on Test set.
"""
from __future__ import annotations

import math
import os
import tempfile
import warnings
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Literal

import matplotlib
os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="mplconfig-"))
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Fixed constants ────────────────────────────────────────────────────────────
PRICE_CACHE_DIR   = Path("data/price_cache")
START_DATE        = "2020-01-01"
END_DATE          = "2025-12-31"
SPLIT_DATE        = "2023-01-01"
LOOKBACK          = 90
RECENT_DAYS       = 5
SCAN_INTERVAL_DAYS = 5
INITIAL_CAPITAL   = 1_000_000.0
POSITION_PCT      = 0.10
MAX_POSITIONS     = 10
CORR_THRESHOLD    = 0.75
EXIT_Z            = 0.3
MIN_DAILY_TURNOVER = 5_000_000.0
MIN_OBSERVATIONS  = 60
RISK_FREE_RATE    = 0.015
TRADING_DAYS      = 252
BUY_FEE           = 0.001425
SELL_FEE          = 0.001425
SELL_TAX          = 0.003

# ── Search space ───────────────────────────────────────────────────────────────
ENTRY_Z_VALUES      = [1.5, 2.0, 2.5]
MAX_HOLD_VALUES     = [15, 20, 30]
STOP_LOSS_VALUES    = [-0.05, -0.08, -0.10]


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
    result: dict[str, pd.DataFrame] = {}
    for f in sorted(PRICE_CACHE_DIR.glob("*.parquet")):
        stock_id = f.stem.split("_")[0]
        try:
            df = pd.read_parquet(f)
        except Exception:
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
    closes, volumes = [], []
    for sid, df in prices.items():
        closes.append(df["close"].rename(sid))
        volumes.append(df["volume"].rename(sid))
    cp = pd.concat(closes, axis=1).sort_index()
    vp = pd.concat(volumes, axis=1).sort_index()
    cp = cp.loc[cp.index <= pd.Timestamp(END_DATE)]
    vp = vp.reindex(cp.index)
    return cp, vp


def pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def compute_deviation(returns: pd.DataFrame, stock_a: str, stock_b: str) -> float:
    spread = (returns[stock_a] - returns[stock_b]).dropna()
    if len(spread) < RECENT_DAYS + 10:
        return float("nan")
    hist = spread.iloc[:-RECENT_DAYS]
    hist_std = hist.std()
    if not np.isfinite(hist_std) or hist_std <= 0:
        return float("nan")
    recent_mean = spread.iloc[-RECENT_DAYS:].mean()
    deviation = (recent_mean - hist.mean()) / hist_std
    return float(deviation) if np.isfinite(deviation) else float("nan")


def scan_pairs(
    close_window: pd.DataFrame,
    volume_window: pd.DataFrame,
    active_pairs: set[tuple[str, str]],
    entry_z: float,
) -> list[dict]:
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
    cols = np.asarray(corr_matrix.columns)
    cv = corr_matrix.to_numpy(dtype=float)
    ui, uj = np.triu_indices_from(cv, k=1)
    sel = np.where(cv[ui, uj] >= CORR_THRESHOLD)[0]
    candidates = []
    for idx in sel:
        a, b = str(cols[ui[idx]]), str(cols[uj[idx]])
        k = pair_key(a, b)
        if k in active_pairs:
            continue
        dev = compute_deviation(returns, a, b)
        if not np.isfinite(dev) or abs(dev) < entry_z:
            continue
        candidates.append({"stock_a": a, "stock_b": b, "correlation": float(cv[ui[idx], uj[idx]]), "deviation": dev})
    candidates.sort(key=lambda r: abs(float(r["deviation"])), reverse=True)
    return candidates


def mark_pair_pnl_pct(pos: Position, prices: pd.Series) -> float:
    lp = float(prices.get(pos.long_stock, np.nan))
    sp = float(prices.get(pos.short_stock, np.nan))
    if not np.isfinite(lp) or not np.isfinite(sp):
        return 0.0
    long_pnl = (lp / pos.entry_long_price - 1.0) * pos.leg_notional
    short_pnl = (pos.entry_short_price / sp - 1.0) * pos.leg_notional
    return (long_pnl + short_pnl) / pos.notional


def close_position(pos: Position, exit_date: pd.Timestamp, exit_dev: float, reason: str, prices: pd.Series):
    le = float(prices[pos.long_stock])
    se = float(prices[pos.short_stock])
    long_gross = (le / pos.entry_long_price - 1.0) * pos.leg_notional
    short_gross = (pos.entry_short_price / se - 1.0) * pos.leg_notional
    exit_cost = pos.leg_notional * (SELL_FEE + SELL_TAX) + pos.leg_notional * BUY_FEE
    net_pnl = long_gross + short_gross - pos.entry_cost - exit_cost
    trade = {
        "pair": f"{pos.stock_a}-{pos.stock_b}",
        "entry_date": pos.entry_date,
        "exit_date": exit_date,
        "hold_days": int((exit_date - pos.entry_date).days),
        "pnl_pct": net_pnl / pos.notional * 100.0,
        "exit_reason": reason,
    }
    return trade, net_pnl


def open_position(cand: dict, date: pd.Timestamp, prices: pd.Series, equity: float) -> Position | None:
    a, b = str(cand["stock_a"]), str(cand["stock_b"])
    dev = float(cand["deviation"])
    pa, pb = float(prices.get(a, np.nan)), float(prices.get(b, np.nan))
    if not np.isfinite(pa) or not np.isfinite(pb) or pa <= 0 or pb <= 0:
        return None
    notional = equity * POSITION_PCT
    leg = notional / 2.0
    if dev > 0:
        direction, short_s, long_s = "SHORT_A_LONG_B", a, b
        esp, elp = pa, pb
    else:
        direction, short_s, long_s = "SHORT_B_LONG_A", b, a
        esp, elp = pb, pa
    entry_cost = leg * (SELL_FEE + SELL_TAX) + leg * BUY_FEE
    return Position(
        pair_key=pair_key(a, b), stock_a=a, stock_b=b, direction=direction,
        entry_date=date, entry_dev=dev, notional=notional, leg_notional=leg,
        entry_long_price=elp, entry_short_price=esp,
        long_stock=long_s, short_stock=short_s, entry_cost=entry_cost,
    )


def run_backtest(
    close_pivot: pd.DataFrame,
    volume_pivot: pd.DataFrame,
    entry_z: float,
    max_hold_days: int,
    stop_loss_pct: float,
) -> tuple[pd.DataFrame, pd.Series]:
    start_ts, end_ts = pd.Timestamp(START_DATE), pd.Timestamp(END_DATE)
    close_ffill = close_pivot.ffill()
    dates = close_ffill.loc[(close_ffill.index >= start_ts) & (close_ffill.index <= end_ts)].index
    date_to_pos = {d: i for i, d in enumerate(close_ffill.index)}

    cash = INITIAL_CAPITAL
    positions: list[Position] = []
    trades: list[dict] = []
    equity_pts: list[tuple] = []
    last_candidates: list[dict] = []

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
            mark_pnl = mark_pair_pnl_pct(position, prices)
            reason = ""
            if np.isfinite(exit_dev) and abs(exit_dev) < EXIT_Z:
                reason = "mean_reversion"
            elif hold_days >= max_hold_days:
                reason = "max_hold_days"
            elif mark_pnl < stop_loss_pct:
                reason = "stop_loss"
            if reason:
                t, net = close_position(position, date, exit_dev, reason, prices)
                trades.append(t)
                cash += net
            else:
                remaining.append(position)
        positions = remaining

        active_pairs = {p.pair_key for p in positions}
        if step % SCAN_INTERVAL_DAYS == 0:
            last_candidates = scan_pairs(hist_close, hist_volume, active_pairs, entry_z)

        unrealized = sum(mark_pair_pnl_pct(p, prices) * p.notional for p in positions)
        equity = cash + unrealized

        for cand in last_candidates:
            if len(positions) >= MAX_POSITIONS:
                break
            k = pair_key(str(cand["stock_a"]), str(cand["stock_b"]))
            if k in active_pairs:
                continue
            p = open_position(cand, date, prices, equity)
            if p is None:
                continue
            positions.append(p)
            active_pairs.add(p.pair_key)
            cash -= p.entry_cost

        unrealized = sum(mark_pair_pnl_pct(p, prices) * p.notional for p in positions)
        equity_pts.append((date, cash + unrealized))

    # Force-close remaining
    if positions and len(dates) > 0:
        final_date = dates[-1]
        prices = close_ffill.loc[final_date]
        fp = date_to_pos[final_date]
        fh = close_ffill.iloc[max(0, fp - LOOKBACK):fp + 1]
        fr = fh.dropna(thresh=MIN_OBSERVATIONS, axis=1).ffill().pct_change().dropna(how="all")
        for position in positions:
            ed = compute_deviation(fr, position.stock_a, position.stock_b)
            if np.isfinite(prices.get(position.long_stock, np.nan)) and np.isfinite(prices.get(position.short_stock, np.nan)):
                t, net = close_position(position, final_date, ed, "end_of_backtest", prices)
                trades.append(t)
                cash += net

    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame(
        columns=["pair", "entry_date", "exit_date", "hold_days", "pnl_pct", "exit_reason"]
    )
    eq = pd.Series(
        [v for _, v in equity_pts],
        index=pd.DatetimeIndex([d for d, _ in equity_pts], name="date"),
        name="equity",
    )
    return trades_df, eq


# ── Metrics ────────────────────────────────────────────────────────────────────
def max_drawdown(eq: pd.Series) -> float:
    if eq.empty:
        return 0.0
    return float((eq / eq.cummax() - 1.0).min())


def sharpe(eq: pd.Series) -> float:
    d = eq.pct_change().dropna()
    if d.empty or d.std() == 0:
        return 0.0
    return float(math.sqrt(TRADING_DAYS) * (d - RISK_FREE_RATE / TRADING_DAYS).mean() / d.std())


def annual_return(eq: pd.Series) -> float:
    if len(eq) < 2:
        return 0.0
    tr = eq.iloc[-1] / eq.iloc[0] - 1.0
    days = max((eq.index[-1] - eq.index[0]).days, 1)
    return float((1.0 + tr) ** (365.25 / days) - 1.0)


def profit_factor(pnls: pd.Series) -> float:
    g, l = pnls[pnls > 0].sum(), pnls[pnls < 0].sum()
    return float(g / abs(l)) if l != 0 else (float("inf") if g > 0 else 0.0)


def summarize(eq: pd.Series, trades: pd.DataFrame) -> dict:
    if eq.empty or trades.empty:
        return {"sharpe": -99, "mdd": -99, "win_rate": 0, "annual_ret": -99, "pf": 0, "trades": 0}
    pnl = trades["pnl_pct"] / 100.0
    return {
        "sharpe": sharpe(eq),
        "mdd": max_drawdown(eq) * 100,
        "win_rate": (pnl > 0).mean() * 100,
        "annual_ret": annual_return(eq) * 100,
        "pf": profit_factor(pnl),
        "trades": len(trades),
    }


def plot_best(eq: pd.Series, label: str) -> None:
    split = pd.Timestamp(SPLIT_DATE)
    fig, ax = plt.subplots(figsize=(12, 6))
    train = eq[eq.index < split]
    test = eq[eq.index >= split]
    if not train.empty:
        ax.plot(train.index, train.values, label="Train", color="#2f6fdd", linewidth=1.8)
    if not test.empty:
        ax.plot(test.index, test.values, label="Test", color="#d14b3f", linewidth=1.8)
    ax.axvline(split, color="#444", linestyle="--", linewidth=1.0, label="Split")
    ax.set_title(f"Best Pairs Strategy: {label}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity (TWD)")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig("pairs_gs_best_equity.png", dpi=160)
    plt.close(fig)
    print("Saved: pairs_gs_best_equity.png")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    print("Loading parquet price cache...")
    prices = load_all_prices()
    if not prices:
        raise RuntimeError(f"No parquet files found under {PRICE_CACHE_DIR}")
    print(f"Loaded {len(prices)} stocks. Building price matrices...")
    close_pivot, volume_pivot = build_pivots(prices)
    print(f"Price matrix: {close_pivot.shape[0]} dates × {close_pivot.shape[1]} stocks")

    split = pd.Timestamp(SPLIT_DATE)
    combos = list(product(ENTRY_Z_VALUES, MAX_HOLD_VALUES, STOP_LOSS_VALUES))
    total = len(combos)
    results = []

    print(f"\nRunning {total} parameter combinations...\n")

    for i, (ez, mh, sl) in enumerate(combos, 1):
        label = f"EntryZ={ez} MaxHold={mh} SL={abs(sl)*100:.0f}%"
        print(f"[{i:2d}/{total}] {label} ...", end=" ", flush=True)

        trades_df, eq = run_backtest(close_pivot, volume_pivot, entry_z=ez, max_hold_days=mh, stop_loss_pct=sl)

        if not trades_df.empty:
            trades_df["exit_date"] = pd.to_datetime(trades_df["exit_date"])

        train_eq = eq[eq.index < split]
        test_eq  = eq[eq.index >= split]
        train_tr = trades_df[trades_df["exit_date"] < split] if not trades_df.empty else trades_df
        test_tr  = trades_df[trades_df["exit_date"] >= split] if not trades_df.empty else trades_df

        tr_stats = summarize(train_eq, train_tr)
        te_stats = summarize(test_eq, test_tr)

        results.append({
            "entry_z": ez, "max_hold": mh, "stop_loss": sl,
            "label": label,
            "train_sharpe": tr_stats["sharpe"],
            "train_mdd": tr_stats["mdd"],
            "train_win": tr_stats["win_rate"],
            "train_ann": tr_stats["annual_ret"],
            "train_pf": tr_stats["pf"],
            "train_trades": tr_stats["trades"],
            "test_sharpe": te_stats["sharpe"],
            "test_mdd": te_stats["mdd"],
            "test_win": te_stats["win_rate"],
            "test_ann": te_stats["annual_ret"],
            "test_pf": te_stats["pf"],
            "test_trades": te_stats["trades"],
            "_eq": eq,
        })

        print(f"Train Sharpe={tr_stats['sharpe']:+.2f} MDD={tr_stats['mdd']:.1f}% WR={tr_stats['win_rate']:.1f}%  |  "
              f"Test Sharpe={te_stats['sharpe']:+.2f} MDD={te_stats['mdd']:.1f}% WR={te_stats['win_rate']:.1f}%")

    # Sort by train Sharpe
    results.sort(key=lambda r: r["train_sharpe"], reverse=True)

    print("\n" + "=" * 100)
    print(f"{'#':>2}  {'EntryZ':>6} {'MaxHold':>7} {'SL':>5}  "
          f"{'Tr Sharpe':>9} {'Tr MDD%':>7} {'Tr WR%':>6} {'Tr PF':>5}  "
          f"{'Te Sharpe':>9} {'Te MDD%':>7} {'Te WR%':>6} {'Te PF':>5}")
    print("-" * 100)
    for rank, r in enumerate(results, 1):
        print(f"{rank:2d}  {r['entry_z']:>6.1f} {r['max_hold']:>7d} {abs(r['stop_loss'])*100:>4.0f}%  "
              f"{r['train_sharpe']:>+9.2f} {r['train_mdd']:>7.1f} {r['train_win']:>6.1f} {r['train_pf']:>5.2f}  "
              f"{r['test_sharpe']:>+9.2f} {r['test_mdd']:>7.1f} {r['test_win']:>6.1f} {r['test_pf']:>5.2f}")

    print("=" * 100)

    # Best by train Sharpe
    best = results[0]
    print(f"\n★ Best (Train Sharpe): {best['label']}")
    print(f"  Train → Sharpe={best['train_sharpe']:+.2f}, MDD={best['train_mdd']:.1f}%, "
          f"WR={best['train_win']:.1f}%, Ann={best['train_ann']:.1f}%, PF={best['train_pf']:.2f}, Trades={best['train_trades']}")
    print(f"  Test  → Sharpe={best['test_sharpe']:+.2f}, MDD={best['test_mdd']:.1f}%, "
          f"WR={best['test_win']:.1f}%, Ann={best['test_ann']:.1f}%, PF={best['test_pf']:.2f}, Trades={best['test_trades']}")

    # Meets criteria?
    criteria = best["test_sharpe"] > 0.5 and best["test_mdd"] > -20 and best["test_win"] > 45
    print(f"\n  成功標準（Test set）: Sharpe>0.5 MDD<20% WR>45% → {'✅ 達標' if criteria else '❌ 未達標'}")

    # Save equity curve for best combo
    plot_best(best["_eq"], best["label"])

    # Save results table
    out_cols = ["label", "train_sharpe", "train_mdd", "train_win", "train_pf",
                "test_sharpe", "test_mdd", "test_win", "test_pf"]
    pd.DataFrame([{k: r[k] for k in out_cols} for r in results]).to_csv(
        "pairs_gs_results.csv", index=False
    )
    print("Saved: pairs_gs_results.csv")


if __name__ == "__main__":
    main()

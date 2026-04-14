"""
Monthly Revenue Momentum Backtest
Strategy: Buy top 20% stocks by RevenueYoY each month.
Train: 2019-2022 / Test: 2023-2025
"""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# --- Config ---
UNIVERSE_PATH = "/tmp/tw_universe_all.json"
PRICE_CACHE_DIR = Path("data/price_cache")
REVENUE_CACHE_DIR = Path("data/revenue_cache")
INITIAL_CAPITAL = 1_000_000
BUY_COST = 0.001425
SELL_COST = 0.001425 + 0.003  # incl. tax
TOP_PCT = 0.20
MIN_AVG_TURNOVER = 5_000_000  # 500萬
TRAIN_END = "2022-12-31"
TEST_START = "2023-01-01"
TWII_ID = "^TWII"  # yfinance ticker for TWSE index
MA_PERIOD = 200

# --- Load universe ---
def load_universe():
    data = json.loads(Path(UNIVERSE_PATH).read_text())
    return {s["id"]: s["market"] for s in data["stocks"]}

# --- Load all revenue data ---
def load_revenue(universe):
    frames = []
    for sid in universe:
        p = REVENUE_CACHE_DIR / f"{sid}.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            df["stock_id"] = sid
            frames.append(df)
    if not frames:
        raise RuntimeError("No revenue cache found. Run fetch_revenue.py first.")
    rev = pd.concat(frames, ignore_index=True)
    rev["date"] = pd.to_datetime(rev["date"])
    rev["revenue"] = pd.to_numeric(rev["revenue"], errors="coerce")
    return rev

# --- Load price data for one stock ---
def load_price(sid, market):
    p = PRICE_CACHE_DIR / f"{sid}_{market}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df

# --- Load TWII index for regime filter ---
def load_twii():
    try:
        import yfinance as yf
        df = yf.download("^TWII", start="2018-01-01", end="2025-12-31", progress=False, auto_adjust=True)
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]
        df = df[["close"]].copy()
        df.index = pd.to_datetime(df.index.tz_localize(None) if df.index.tz else df.index)
        df["ma200"] = df["close"].rolling(MA_PERIOD).mean()
        return df
    except Exception as e:
        print(f"Warning: TWII load failed ({e}), regime filter disabled")
        return None

# --- Build trading calendar ---
def build_calendar(universe):
    dates = set()
    for sid, mkt in list(universe.items())[:50]:  # sample for speed
        p = PRICE_CACHE_DIR / f"{sid}_{mkt}.parquet"
        if p.exists():
            df = pd.read_parquet(p, columns=["date"])
            dates.update(pd.to_datetime(df["date"]).tolist())
    return sorted(dates)

# --- Get next trading day on or after target date ---
def next_trading_day(target, calendar):
    for d in calendar:
        if d >= target:
            return d
    return None

# --- Compute RevenueYoY ---
def compute_yoy(rev):
    rev = rev.sort_values(["stock_id", "date"])
    rev["year"] = rev["date"].dt.year
    rev["month"] = rev["date"].dt.month
    rev["prev_year_rev"] = rev.groupby(["stock_id", "month"])["revenue"].shift(1)
    rev["yoy"] = rev["revenue"] / rev["prev_year_rev"] - 1
    # Filter extremes
    rev = rev[(rev["yoy"] > -0.5) & (rev["yoy"] < 5.0)]
    return rev

# --- Run backtest ---
def run_backtest(rebalance_dates, revenue_by_month, universe, price_cache, period_name, twii=None):
    capital = INITIAL_CAPITAL
    equity_curve = []
    all_trades = []
    monthly_returns = []

    holdings = {}  # stock_id -> {shares, entry_price, entry_date, yoy}

    for i, rb_date in enumerate(rebalance_dates[:-1]):
        next_rb = rebalance_dates[i + 1]
        year, month = rb_date.year, rb_date.month

        # Regime filter: skip if TWII below 200MA
        if twii is not None:
            mask = twii.index <= rb_date
            if mask.any():
                row_tw = twii[mask].iloc[-1]
                close_val = float(row_tw["close"])
                ma200_val = row_tw["ma200"]
                in_downtrend = (not pd.isna(ma200_val)) and (close_val < float(ma200_val))
            else:
                in_downtrend = False
            if in_downtrend:
                    # Market in downtrend: sell and hold cash
                    sell_proceeds = 0
                    for sid, pos in holdings.items():
                        px = price_cache.get(sid)
                        if px is not None and rb_date in px.index:
                            ep = px.loc[rb_date, "open"] if "open" in px.columns else px.loc[rb_date, "close"]
                            gross = pos["shares"] * ep
                            sell_proceeds += gross * (1 - SELL_COST)
                    capital += sell_proceeds
                    holdings = {}
                    equity_curve.append((rb_date, capital))
                    continue

        # Revenue signal: use data announced in current month (by the 10th, we trade on the 11th)
        rev_month = revenue_by_month.get((rb_date.year, rb_date.month), pd.DataFrame())

        # Sell existing holdings at rb_date open (current rebalance day)
        sell_proceeds = 0
        for sid, pos in holdings.items():
            px = price_cache.get(sid)
            if px is None or rb_date not in px.index:
                # fallback: use last known close
                try:
                    exit_price = px.iloc[px.index.get_loc(rb_date, method="ffill")]["close"]
                except Exception:
                    continue
            else:
                exit_price = px.loc[rb_date, "open"] if "open" in px.columns else px.loc[rb_date, "close"]
            shares = pos["shares"]
            gross = shares * exit_price
            cost = gross * SELL_COST
            net = gross - cost
            sell_proceeds += net
            pnl = net - pos["cost_basis"]
            ret_pct = pnl / pos["cost_basis"] if pos["cost_basis"] > 0 else 0
            all_trades.append({
                "rebalance_date": rb_date,
                "stock_id": sid,
                "revenue_yoy": pos["yoy"],
                "entry_price": pos["entry_price"],
                "exit_price": exit_price,
                "return_pct": ret_pct,
                "pnl": pnl,
            })

        capital += sell_proceeds

        # Select new stocks
        if rev_month.empty:
            holdings = {}
            equity_curve.append((rb_date, capital))
            if i > 0:
                monthly_returns.append(0)
            continue

        # Liquidity filter
        candidates = []
        for _, row in rev_month.iterrows():
            sid = row["stock_id"]
            mkt = universe.get(sid)
            px = price_cache.get(sid)
            if px is None or rb_date not in px.index:
                continue
            # avg turnover last 20 days
            idx = px.index.get_loc(rb_date)
            window = px.iloc[max(0, idx-20):idx]
            if len(window) < 5:
                continue
            avg_turnover = (window["close"] * window["volume"]).mean()
            if avg_turnover < MIN_AVG_TURNOVER:
                continue
            candidates.append((sid, row["yoy"], avg_turnover))

        if not candidates:
            holdings = {}
            equity_curve.append((rb_date, capital))
            if i > 0:
                monthly_returns.append(0)
            continue

        cand_df = pd.DataFrame(candidates, columns=["stock_id", "yoy", "turnover"])
        cand_df = cand_df.sort_values("yoy", ascending=False)
        n_select = max(1, int(len(cand_df) * TOP_PCT))
        selected = cand_df.head(n_select)

        # Buy at rb_date open
        prev_capital = capital
        alloc = capital / len(selected)
        new_holdings = {}
        total_spent = 0

        for _, row in selected.iterrows():
            sid = row["stock_id"]
            px = price_cache.get(sid)
            if px is None or rb_date not in px.index:
                continue
            entry_price = px.loc[rb_date, "open"] if "open" in px.columns else px.loc[rb_date, "close"]
            if entry_price <= 0:
                continue
            cost = alloc * BUY_COST
            investable = alloc - cost
            shares = int(investable / entry_price)
            if shares <= 0:
                continue
            cost_basis = shares * entry_price * (1 + BUY_COST)
            new_holdings[sid] = {
                "shares": shares,
                "entry_price": entry_price,
                "cost_basis": cost_basis,
                "yoy": row["yoy"],
            }
            total_spent += cost_basis

        holdings = new_holdings
        capital = capital - total_spent  # remaining cash

        # Mark equity
        port_value = capital
        for sid, pos in holdings.items():
            px = price_cache.get(sid)
            if px is not None and rb_date in px.index:
                price = px.loc[rb_date, "close"]
                port_value += pos["shares"] * price

        equity_curve.append((rb_date, port_value))

    # Derive monthly returns from equity curve (correct denominator)
    for i in range(1, len(equity_curve)):
        prev_val = equity_curve[i-1][1]
        curr_val = equity_curve[i][1]
        if prev_val > 0:
            monthly_returns.append((curr_val - prev_val) / prev_val)

    return equity_curve, monthly_returns, all_trades

# --- Performance metrics ---
def calc_metrics(equity_curve, monthly_returns, period_name):
    if not equity_curve:
        print(f"=== {period_name} === No data")
        return

    dates = [e[0] for e in equity_curve]
    values = [e[1] for e in equity_curve]
    total_ret = (values[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL
    n_months = len(monthly_returns)
    years = n_months / 12
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0

    mr = np.array(monthly_returns)
    sharpe = (mr.mean() / mr.std() * np.sqrt(12)) if mr.std() > 0 else 0

    eq = np.array(values)
    rolling_max = np.maximum.accumulate(eq)
    drawdowns = (eq - rolling_max) / rolling_max
    max_dd = drawdowns.min()

    profits = mr[mr > 0].sum()
    losses = abs(mr[mr < 0].sum())
    pf = profits / losses if losses > 0 else float("inf")

    print(f"\n=== {period_name} ===")
    print(f"再平衡次數:   {len(equity_curve)}")
    print(f"總報酬:       {total_ret*100:.1f}%")
    print(f"年化報酬:     {ann_ret*100:.1f}%")
    print(f"Sharpe:       {sharpe:.2f}")
    print(f"Max Drawdown: {max_dd*100:.1f}%")
    print(f"Profit Factor:{pf:.2f}")

    return dates, values

# --- Main ---
def main():
    print("Loading universe...")
    universe = load_universe()

    print("Loading revenue data...")
    rev = load_revenue(universe)
    rev_yoy = compute_yoy(rev)

    # Group revenue by (year, month)
    revenue_by_month = {}
    for (yr, mo), grp in rev_yoy.groupby(["year", "month"]):
        revenue_by_month[(yr, mo)] = grp[["stock_id", "yoy"]].dropna()

    print("Loading price cache...")
    price_cache = {}
    for sid, mkt in universe.items():
        df = load_price(sid, mkt)
        if df is not None:
            price_cache[sid] = df

    print("Loading TWII for regime filter...")
    twii = load_twii()

    print("Building calendar...")
    calendar = build_calendar(universe)
    calendar = [pd.Timestamp(d) for d in calendar]

    # Rebalance dates: 11th of each month (next trading day)
    all_months = pd.date_range("2019-01-01", "2025-12-01", freq="MS")
    rebalance_dates = []
    for m in all_months:
        target = m.replace(day=11)
        nd = next_trading_day(target, calendar)
        if nd:
            rebalance_dates.append(nd)

    train_dates = [d for d in rebalance_dates if d <= pd.Timestamp(TRAIN_END)]
    test_dates = [d for d in rebalance_dates if d >= pd.Timestamp(TEST_START)]

    print("Running TRAIN backtest (2019-2022)...")
    train_eq, train_mr, train_trades = run_backtest(train_dates, revenue_by_month, universe, price_cache, "TRAIN", twii=twii)
    train_result = calc_metrics(train_eq, train_mr, "TRAIN (2019-2022)")

    print("Running TEST backtest (2023-2025)...")
    test_eq, test_mr, test_trades = run_backtest(test_dates, revenue_by_month, universe, price_cache, "TEST", twii=twii)
    test_result = calc_metrics(test_eq, test_mr, "TEST (2023-2025)")

    # Save trades
    all_trades = train_trades + test_trades
    if all_trades:
        pd.DataFrame(all_trades).to_csv("revenue_backtest_trades.csv", index=False)
        print("\nTrades saved: revenue_backtest_trades.csv")

    # Plot equity curve
    fig, ax = plt.subplots(figsize=(12, 5))
    if train_eq:
        td, tv = zip(*train_eq)
        ax.plot(td, tv, color="cyan", label="Train (2019-2022)")
    if test_eq:
        td2, tv2 = zip(*test_eq)
        ax.plot(td2, tv2, color="lime", label="Test (2023-2025)")
        ax.axvline(pd.Timestamp(TEST_START), color="gray", linestyle="--", alpha=0.7)
    ax.set_title("Revenue Momentum Strategy — Equity Curve")
    ax.set_ylabel("Portfolio Value (TWD)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("revenue_backtest_equity.png", dpi=150)
    print("Chart saved: revenue_backtest_equity.png")

if __name__ == "__main__":
    main()

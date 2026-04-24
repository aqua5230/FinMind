"""
Strength pullback backtest for Taiwan stocks.

This is a separate strategy from the RSI falling-knife baseline. It only buys
stocks that were already in an uptrend, pulled back moderately, and then
confirmed renewed strength.
"""
import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

UNIVERSE_PATH = "/tmp/tw_universe_all.json"
PRICE_CACHE_DIR = Path("data/price_cache")

START_DATE = "2018-01-01"
END_DATE = "2025-12-31"
SPLIT_DATE = "2023-01-01"

INITIAL_CAPITAL = 1_000_000.0
POSITION_PCT = 0.10
MAX_POSITIONS = 5
COOLDOWN_DAYS = 20

BUY_FEE_RATE = 0.001425
SELL_FEE_RATE = 0.001425
SELL_TAX_RATE = 0.003

MIN_CLOSE = 10.0
MIN_AVG_TURNOVER_20 = 30_000_000.0

MIN_120D_RETURN = 0.20
PULLBACK_MIN = 0.08
PULLBACK_MAX = 0.18
RSI_MIN = 35.0
RSI_MAX = 55.0

ATR_STOP_MULT = 2.0
TAKE_PROFIT_PCT = 0.20
MAX_HOLD_DAYS = 30

TRADES_CSV = "strength_pullback_trades.csv"
EQUITY_PNG = "strength_pullback_equity.png"
REPORT_JSON = "strength_pullback_report.json"


@dataclass(frozen=True)
class Signal:
    stock_id: str
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    entry_index: int
    setup_low: float
    atr14: float


def wilder_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(close)
    rsi = np.full(n, np.nan)
    if n <= period:
        return rsi
    delta = np.diff(close, prepend=close[0])
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    avg_gain = gains[1:period + 1].mean()
    avg_loss = losses[1:period + 1].mean()
    for i in range(period, n):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i] = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - 100.0 / (1.0 + rs)
    return rsi


def load_universe() -> list[dict]:
    with open(UNIVERSE_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["stocks"]


def cache_path(stock_id: str, market: str) -> Path:
    return PRICE_CACHE_DIR / f"{stock_id}_{market}.parquet"


def read_prices(stock: dict) -> Optional[pd.DataFrame]:
    path = cache_path(str(stock["id"]), str(stock["market"]))
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna().sort_values("date").reset_index(drop=True)
    valid = (
        (df["open"] > 0)
        & (df["high"] > 0)
        & (df["low"] > 0)
        & (df["close"] > 0)
        & (df["volume"] >= 0)
        & (df["high"] >= df["low"])
        & (df["high"] >= df[["open", "close"]].max(axis=1))
        & (df["low"] <= df[["open", "close"]].min(axis=1))
    )
    df = df.loc[valid].copy().reset_index(drop=True)
    if len(df) < 260:
        return None
    return df


def normalize_yfinance_columns(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.copy()
    raw.columns = [
        c[0].lower() if isinstance(c, tuple) else str(c).lower()
        for c in raw.columns
    ]
    raw = raw.reset_index()
    raw = raw.rename(columns={"Date": "date", "datetime": "date"})
    df = raw[["date", "open", "high", "low", "close", "volume"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna().sort_values("date").reset_index(drop=True)


def load_market_proxy() -> Optional[pd.DataFrame]:
    stock = {"id": "0050", "market": "TWSE"}
    cached = read_prices(stock)
    if cached is not None:
        return add_indicators(cached)

    raw = yf.download(
        "0050.TW",
        start=START_DATE,
        end=END_DATE,
        progress=False,
        auto_adjust=True,
    )
    if raw.empty:
        return None
    df = normalize_yfinance_columns(raw)
    PRICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path("0050", "TWSE"), index=False)
    return add_indicators(df)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    prev_close = close.shift(1)

    df["ma5"] = close.rolling(5).mean()
    df["ma20"] = close.rolling(20).mean()
    df["ma60"] = close.rolling(60).mean()
    df["ma200"] = close.rolling(200).mean()
    df["high20"] = close.rolling(20).max()
    df["ret120"] = close / close.shift(120) - 1.0
    df["avg_turnover20"] = (close * df["volume"]).rolling(20).mean()
    df["rsi14"] = wilder_rsi(close.to_numpy(dtype=float), 14)

    true_range = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr14"] = true_range.rolling(14).mean()
    df["pullback20"] = (df["high20"] - close) / df["high20"]
    return df


def load_all_data(stocks: list[dict]) -> Dict[str, pd.DataFrame]:
    all_data: Dict[str, pd.DataFrame] = {}
    for idx, stock in enumerate(stocks, start=1):
        df = read_prices(stock)
        if df is not None:
            all_data[str(stock["id"])] = add_indicators(df)
        if idx == 1 or idx % 100 == 0 or idx == len(stocks):
            print(f"Loaded {idx}/{len(stocks)} stocks; valid={len(all_data)}", flush=True)
    return all_data


def build_market_filter(all_data: Dict[str, pd.DataFrame]) -> set[pd.Timestamp]:
    # 0050 is a stable proxy for broad Taiwan market regime in the existing cache.
    market = all_data.get("0050") or load_market_proxy()
    if market is None:
        return set()
    ok = market.loc[market["close"] > market["ma200"], "date"]
    return {pd.Timestamp(d) for d in ok}


def generate_signals_for_stock(stock_id: str, df: pd.DataFrame, market_ok_dates: set[pd.Timestamp]) -> list[Signal]:
    signals: list[Signal] = []
    for i in range(201, len(df) - 1):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        signal_date = pd.Timestamp(row["date"])
        if signal_date not in market_ok_dates:
            continue
        if row["close"] < MIN_CLOSE:
            continue
        if row["avg_turnover20"] < MIN_AVG_TURNOVER_20:
            continue
        if not (row["close"] > row["ma200"] and row["ma60"] > row["ma200"]):
            continue
        if row["ret120"] < MIN_120D_RETURN:
            continue
        if not (PULLBACK_MIN <= row["pullback20"] <= PULLBACK_MAX):
            continue
        if not (RSI_MIN <= row["rsi14"] <= RSI_MAX):
            continue
        # Confirmation: buyers regained short-term control.
        if not (row["close"] > row["ma5"] and row["close"] > prev["high"] and row["close"] > row["open"]):
            continue
        if np.isnan(row["atr14"]) or row["atr14"] <= 0:
            continue
        signals.append(
            Signal(
                stock_id=stock_id,
                signal_date=signal_date,
                entry_date=pd.Timestamp(df.iloc[i + 1]["date"]),
                entry_index=i + 1,
                setup_low=float(row["low"]),
                atr14=float(row["atr14"]),
            )
        )
    return signals


def build_signals(all_data: Dict[str, pd.DataFrame]) -> Tuple[list[Signal], list[Signal]]:
    market_ok_dates = build_market_filter(all_data)
    if not market_ok_dates:
        raise RuntimeError("No market filter data. Expected 0050 in price cache.")
    train: list[Signal] = []
    test: list[Signal] = []
    split = pd.Timestamp(SPLIT_DATE)
    for stock_id, df in all_data.items():
        if stock_id == "0050":
            continue
        for signal in generate_signals_for_stock(stock_id, df, market_ok_dates):
            if signal.signal_date < split:
                train.append(signal)
            else:
                test.append(signal)
    train.sort(key=lambda s: (s.entry_date, s.stock_id))
    test.sort(key=lambda s: (s.entry_date, s.stock_id))
    return train, test


def iter_trading_dates(signals: list[Signal], all_data: Dict[str, pd.DataFrame], start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    if not signals:
        return []
    dates = set()
    first = max(min(s.entry_date for s in signals), start)
    for df in all_data.values():
        mask = (df["date"] >= first) & (df["date"] <= end)
        dates.update(pd.Timestamp(d) for d in df.loc[mask, "date"])
    return sorted(dates)


def close_position(position: dict, exit_date: pd.Timestamp, exit_price: float, reason: str) -> tuple[dict, float]:
    gross = exit_price * position["shares"]
    sell_fee = gross * SELL_FEE_RATE
    sell_tax = gross * SELL_TAX_RATE
    cash_in = gross - sell_fee - sell_tax
    invested = position["entry_price"] * position["shares"] + position["buy_fee"]
    pnl = cash_in - invested
    trade = {
        "stock_id": position["stock_id"],
        "entry_date": position["entry_date"],
        "entry_price": position["entry_price"],
        "exit_date": exit_date,
        "exit_price": exit_price,
        "exit_reason": reason,
        "shares": position["shares"],
        "buy_fee": position["buy_fee"],
        "sell_fee": sell_fee,
        "sell_tax": sell_tax,
        "hold_days": int(position["bars_held"]),
        "pnl": pnl,
        "return_pct": (cash_in / invested - 1.0) * 100.0,
    }
    return trade, cash_in


def value_positions(positions: dict[str, dict], data_by_date: dict[str, pd.DataFrame], current_date: pd.Timestamp, price_col: str) -> float:
    value = 0.0
    for stock_id, position in positions.items():
        price = float(position.get("last_close", position["entry_price"]))
        rows = data_by_date.get(stock_id)
        if rows is not None and current_date in rows.index:
            row = rows.loc[current_date]
            price = float(row.get(price_col, row["close"]))
            position["last_close"] = float(row["close"])
        value += price * position["shares"]
    return value


def simulate(signals: list[Signal], all_data: Dict[str, pd.DataFrame], start: str, end: str) -> tuple[list[dict], pd.DataFrame]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    signals = [s for s in signals if start_ts <= s.entry_date <= end_ts]
    signals_by_date: dict[pd.Timestamp, list[Signal]] = {}
    for signal in signals:
        signals_by_date.setdefault(signal.entry_date, []).append(signal)

    data_by_date = {stock_id: df.set_index("date", drop=False) for stock_id, df in all_data.items()}
    trading_dates = iter_trading_dates(signals, all_data, start_ts, end_ts)
    cash = INITIAL_CAPITAL
    positions: dict[str, dict] = {}
    cooldown_until: dict[str, pd.Timestamp] = {}
    trades: list[dict] = []
    equity_rows: list[dict] = []

    for current_date in trading_dates:
        opening_equity = cash + value_positions(positions, data_by_date, current_date, "open")
        target_value = opening_equity * POSITION_PCT

        for signal in signals_by_date.get(current_date, []):
            if signal.stock_id in positions:
                continue
            if current_date <= cooldown_until.get(signal.stock_id, pd.Timestamp.min):
                continue
            if len(positions) >= MAX_POSITIONS:
                continue
            rows = data_by_date.get(signal.stock_id)
            if rows is None or current_date not in rows.index:
                continue
            row = rows.loc[current_date]
            entry_price = float(row["open"])
            if entry_price <= 0 or np.isnan(entry_price):
                continue
            shares = int(target_value // (entry_price * (1.0 + BUY_FEE_RATE)))
            if shares <= 0:
                continue
            gross = entry_price * shares
            buy_fee = gross * BUY_FEE_RATE
            total_cost = gross + buy_fee
            if total_cost > cash:
                continue
            stop_price = max(signal.setup_low, entry_price - ATR_STOP_MULT * signal.atr14)
            if stop_price >= entry_price:
                stop_price = entry_price * 0.93
            cash -= total_cost
            positions[signal.stock_id] = {
                "stock_id": signal.stock_id,
                "entry_date": current_date,
                "entry_price": entry_price,
                "shares": shares,
                "buy_fee": buy_fee,
                "stop_price": stop_price,
                "bars_held": 0,
                "last_close": float(row["close"]),
            }

        for stock_id, position in list(positions.items()):
            rows = data_by_date.get(stock_id)
            if rows is None or current_date not in rows.index:
                continue
            row = rows.loc[current_date]
            low = float(row["low"])
            high = float(row["high"])
            close = float(row["close"])
            ma20 = float(row["ma20"]) if not np.isnan(row["ma20"]) else np.nan
            position["bars_held"] += 1

            exit_price = None
            exit_reason = None
            take_profit_price = position["entry_price"] * (1.0 + TAKE_PROFIT_PCT)
            if low <= position["stop_price"]:
                exit_price = position["stop_price"]
                exit_reason = "stop_loss"
            elif high >= take_profit_price:
                exit_price = take_profit_price
                exit_reason = "take_profit"
            elif not np.isnan(ma20) and close < ma20 and position["bars_held"] >= 3:
                exit_price = close
                exit_reason = "ma20_break"
            elif position["bars_held"] >= MAX_HOLD_DAYS:
                exit_price = close
                exit_reason = "time_stop"

            if exit_price is not None and exit_reason is not None:
                trade, cash_in = close_position(position, current_date, float(exit_price), exit_reason)
                trades.append(trade)
                cash += cash_in
                cooldown_until[stock_id] = current_date + pd.Timedelta(days=COOLDOWN_DAYS)
                del positions[stock_id]

        market_value = value_positions(positions, data_by_date, current_date, "close")
        equity_rows.append(
            {
                "date": current_date,
                "cash": cash,
                "market_value": market_value,
                "equity": cash + market_value,
                "positions": len(positions),
            }
        )

    if positions and trading_dates:
        final_date = trading_dates[-1]
        for stock_id, position in list(positions.items()):
            rows = data_by_date.get(stock_id)
            if rows is None:
                continue
            available = rows[rows.index <= final_date]
            if available.empty:
                continue
            row = available.iloc[-1]
            trade, cash_in = close_position(position, pd.Timestamp(row["date"]), float(row["close"]), "end_of_data")
            trades.append(trade)
            cash += cash_in
            del positions[stock_id]

    equity = pd.DataFrame(equity_rows)
    if equity.empty:
        equity = pd.DataFrame([{"date": start_ts, "cash": INITIAL_CAPITAL, "market_value": 0.0, "equity": INITIAL_CAPITAL, "positions": 0}])
    return trades, equity


def calc_metrics(trades: list[dict], equity: pd.DataFrame) -> dict:
    eq = equity["equity"].astype(float)
    final_capital = float(eq.iloc[-1])
    total_return = (final_capital / INITIAL_CAPITAL - 1.0) * 100.0
    days = max(1, int((equity["date"].iloc[-1] - equity["date"].iloc[0]).days))
    annual_return = ((final_capital / INITIAL_CAPITAL) ** (365.0 / days) - 1.0) * 100.0
    daily_returns = eq.pct_change().dropna()
    peak = eq.cummax()
    max_drawdown = float(((peak - eq) / peak).max() * 100.0)
    sharpe = 0.0
    if len(daily_returns) > 1 and daily_returns.std(ddof=1) > 0:
        sharpe = float(daily_returns.mean() / daily_returns.std(ddof=1) * np.sqrt(252.0))

    returns = np.array([t["return_pct"] for t in trades], dtype=float)
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    pnls = np.array([t["pnl"] for t in trades], dtype=float)
    gross_profit = float(pnls[pnls > 0].sum()) if len(pnls) else 0.0
    gross_loss = float(abs(pnls[pnls < 0].sum())) if len(pnls) else 0.0

    return {
        "start_capital": INITIAL_CAPITAL,
        "final_capital": final_capital,
        "total_return_pct": total_return,
        "annual_return_pct": annual_return,
        "trade_count": len(trades),
        "win_rate_pct": float(len(wins) / len(trades) * 100.0) if trades else 0.0,
        "avg_win_pct": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss_pct": float(losses.mean()) if len(losses) else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else 0.0,
        "max_drawdown_pct": max_drawdown,
        "sharpe_ratio": sharpe,
    }


def trades_to_dataframe(trades: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "股票": t["stock_id"],
                "進場日": pd.Timestamp(t["entry_date"]).strftime("%Y-%m-%d"),
                "進場價": round(float(t["entry_price"]), 4),
                "出場日": pd.Timestamp(t["exit_date"]).strftime("%Y-%m-%d"),
                "出場價": round(float(t["exit_price"]), 4),
                "出場原因": t["exit_reason"],
                "報酬率(%)": round(float(t["return_pct"]), 4),
                "持倉天數": int(t["hold_days"]),
            }
            for t in trades
        ]
    )


def save_equity_plot(equity: pd.DataFrame) -> None:
    plt.figure(figsize=(12, 6))
    plt.plot(equity["date"], equity["equity"], linewidth=1.8)
    plt.title("Strength Pullback Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(EQUITY_PNG, dpi=150)
    plt.close()


def print_summary(label: str, metrics: dict) -> None:
    print(f"\n{label} Summary")
    print(f"起始資金: {metrics['start_capital']:,.0f}")
    print(f"最終資金: {metrics['final_capital']:,.0f}")
    print(f"總報酬%: {metrics['total_return_pct']:.2f}")
    print(f"年化報酬%: {metrics['annual_return_pct']:.2f}")
    print(f"交易次數: {metrics['trade_count']}")
    print(f"勝率%: {metrics['win_rate_pct']:.2f}")
    print(f"平均獲利%: {metrics['avg_win_pct']:.2f}")
    print(f"平均虧損%: {metrics['avg_loss_pct']:.2f}")
    print(f"Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"Max Drawdown%: {metrics['max_drawdown_pct']:.2f}")
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")


def main() -> None:
    stocks = load_universe()
    print(f"Loaded universe: {len(stocks)} stocks")
    all_data = load_all_data(stocks)
    print(f"Loaded valid cached prices: {len(all_data)} stocks")

    train_signals, test_signals = build_signals(all_data)
    print(f"Train signals: {len(train_signals)}")
    print(f"Test signals: {len(test_signals)}")

    train_trades, train_equity = simulate(train_signals, all_data, START_DATE, "2022-12-31")
    test_trades, test_equity = simulate(test_signals, all_data, SPLIT_DATE, END_DATE)
    train_metrics = calc_metrics(train_trades, train_equity)
    test_metrics = calc_metrics(test_trades, test_equity)

    trades_df = trades_to_dataframe(test_trades)
    trades_df.to_csv(TRADES_CSV, index=False, encoding="utf-8-sig")
    save_equity_plot(test_equity)
    report = {
        "strategy": "strength_pullback",
        "params": {
            "market_filter": "0050 close > MA200",
            "min_close": MIN_CLOSE,
            "min_avg_turnover_20": MIN_AVG_TURNOVER_20,
            "min_120d_return": MIN_120D_RETURN,
            "pullback_min": PULLBACK_MIN,
            "pullback_max": PULLBACK_MAX,
            "rsi_min": RSI_MIN,
            "rsi_max": RSI_MAX,
            "atr_stop_mult": ATR_STOP_MULT,
            "take_profit_pct": TAKE_PROFIT_PCT,
            "max_hold_days": MAX_HOLD_DAYS,
            "cooldown_days": COOLDOWN_DAYS,
        },
        "train": train_metrics,
        "test": test_metrics,
    }
    Path(REPORT_JSON).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print_summary("Train", train_metrics)
    print_summary("Test", test_metrics)
    print(f"\nSaved trades CSV: {TRADES_CSV}")
    print(f"Saved equity PNG: {EQUITY_PNG}")
    print(f"Saved report JSON: {REPORT_JSON}")


if __name__ == "__main__":
    main()

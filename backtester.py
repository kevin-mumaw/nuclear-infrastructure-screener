"""
Nuclear Infrastructure Screener — Backtester
Second Layer Capital

Architecture:
  Layer 1 — Price Data      : yfinance daily adjusted close, all active tickers + SGOV.
                               IPO_FLOORS applied to zero out SPAC shell history for
                               OKLO (pre May 2024), GEV (pre Apr 2024), TLN (pre May 2023).
  Layer 2 — Signals         : 60-day ROC momentum + rolling peak drawdown (vectorized,
                               pre-calculated for the full history before the loop)
  Layer 3 — NQS Filter      : Optional quality gate. Valid NQS score → must clear
                               NQS_MIN_THRESHOLD. Null NQS → passes on price signals
                               alone. Never excluded solely for missing NQS data.
                               LOOKAHEAD WARNING: load_nqs_scores() computes
                               TODAY's NQS once and applies it to every trade
                               back to 2022. A gated run is therefore
                               IN-SAMPLE, not a tradable result. main() runs
                               both an ungated (honest) variant and a gated
                               variant labeled "(in-sample)".
  Layer 4 — Position Logic  : Equal-weight qualifying assets, 0.05% slippage on
                               rebalance days, SGOV rotation when nothing qualifies.
  Layer 5 — Metrics         : Total return, annualized vol, Sharpe, max drawdown.
                               Two benchmarks, both aligned to the same trading
                               days as the strategy they are compared with:
                               (a) true buy-and-hold — equal dollars in each
                               ticker valid on the start day, shares fixed,
                               weights drift; (b) daily-rebalanced
                               equal-weight — mean daily return of the valid
                               tickers, rebalanced every day (the ORIGINAL
                               benchmark, kept and labeled honestly).

Momentum windows tested: 14-day (fast), 60-day (institutional), 200-day (macro).
Risk controls: 15% trailing drawdown stop-loss, 100% take-profit, 0.05% slippage.
Defensive asset: SGOV (iShares 0-3 Month Treasury Bond ETF).
"""

import json
import os
import warnings
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Parameters ────────────────────────────────────────────────────────────────

TICKERS = [
    # Domain 1 — Fuel Cycle
    "CCJ", "UEC", "DNN", "LEU",
    # Domain 2 — Components & Grid
    "BWXT", "GEV", "FLS", "IR",
    # Domain 3 — SMR Pure-Plays (exception layer)
    "OKLO", "SMR",
    # Domain 4 — Utilities
    "CEG", "VST", "TLN",
    # Domain 5 — EPC
    "J", "FLR",
]

DEFENSIVE_ASSET  = "SGOV"
START_DATE       = "2022-01-01"
END_DATE         = datetime.today().strftime("%Y-%m-%d")

MOMENTUM_WINDOWS = [14, 60, 200]
DRAWDOWN_LIMIT   = 0.15
TAKE_PROFIT      = 1.00
SLIPPAGE         = 0.0005
RISK_FREE_RATE   = 0.05
NQS_MIN_THRESHOLD = 40

# ── IPO Floor Dates ───────────────────────────────────────────────────────────
# Tickers that traded as SPAC shells before their real operating business listed.
# yfinance returns SPAC NAV (~$10) for these dates — not real price history.
# Any date BEFORE the floor date is forced to NaN in load_prices().
#
#   OKLO : Merged with AltC Acquisition Corp, closed May 10, 2024
#   GEV  : GE Vernova spun off from GE, April 2, 2024
#   TLN  : Talen Energy emerged from bankruptcy, May 17, 2023
#   SMR  : Trading as operating co since May 2022 — no floor needed
IPO_FLOORS = {
    "OKLO": "2024-05-10",
    "GEV":  "2024-04-02",
    "TLN":  "2023-05-17",
}

OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "config", "manual_overrides.json")
CHART_PATH     = "nuclear_backtest_equity_curves.png"

# ── Layer 1: Price Data ───────────────────────────────────────────────────────

def load_prices() -> tuple[pd.DataFrame, pd.Series]:
    all_tickers = TICKERS + [DEFENSIVE_ASSET]
    print(f"[DATA] Downloading price history for {len(all_tickers)} tickers "
          f"({START_DATE} → {END_DATE})...")

    raw = yf.download(all_tickers, start=START_DATE, end=END_DATE,
                      auto_adjust=True, progress=False)["Close"]
    raw = raw.ffill()
    raw = raw.dropna(how="all")

    equity_prices    = raw[TICKERS]
    defensive_prices = raw[DEFENSIVE_ASSET]

    for ticker, floor_date in IPO_FLOORS.items():
        if ticker in equity_prices.columns:
            floor = pd.Timestamp(floor_date)
            equity_prices.loc[equity_prices.index < floor, ticker] = np.nan
            print(f"[DATA] {ticker}: IPO floor applied — "
                  f"data before {floor_date} set to NaN (SPAC shell excluded)")

    print(f"[DATA] Loaded {len(raw)} trading days. "
          f"Earliest: {raw.index[0].date()}, Latest: {raw.index[-1].date()}")

    for t in TICKERS:
        first_valid = equity_prices[t].first_valid_index()
        if first_valid and first_valid > raw.index[0]:
            print(f"[DATA] {t}: history starts {first_valid.date()}")

    return equity_prices, defensive_prices


# ── Layer 2: Signals ──────────────────────────────────────────────────────────

def build_signals(equity_prices: pd.DataFrame, window: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    momentum_scores = equity_prices.pct_change(periods=window)
    rolling_peaks   = equity_prices.cummax()
    asset_drawdowns = (equity_prices - rolling_peaks) / rolling_peaks
    return momentum_scores, asset_drawdowns


# ── Layer 3: NQS Filter ───────────────────────────────────────────────────────

def load_nqs_scores() -> dict:
    """Load TODAY's NQS for every ticker.

    Per-ticker failures score that ticker None (it then passes on price
    signals alone, by design — a missing score never excludes a ticker).
    A TOTAL failure — scorer unimportable, overrides unreadable, or no
    ticker scores at all — raises RuntimeError. The gate must never
    silently vanish: a backtest that quietly drops its quality gate is
    worse than no backtest. Callers that can proceed without the gate
    (main()) catch this, print a loud banner, and run ungated only.
    """
    try:
        from scoring.nqs_scorer import calculate_nqs
    except Exception as e:
        raise RuntimeError(
            "NQS gate unavailable: cannot import scoring.nqs_scorer "
            f"({e}). Refusing to run a gated backtest on price signals alone."
        ) from e

    overrides = {}
    if os.path.exists(OVERRIDES_PATH):
        try:
            with open(OVERRIDES_PATH) as f:
                overrides = json.load(f)
        except Exception as e:
            raise RuntimeError(
                f"NQS gate unavailable: cannot read {OVERRIDES_PATH} ({e})."
            ) from e

    scores = {}
    failures = {}
    for ticker in TICKERS:
        try:
            result = calculate_nqs(ticker, overrides)
            scores[ticker] = result.get("nqs")
        except Exception as e:
            scores[ticker] = None
            failures[ticker] = str(e)

    for ticker, err in failures.items():
        print(f"[NQS] {ticker}: score failed ({err}) — passes on price signals alone.")

    if all(v is None for v in scores.values()):
        raise RuntimeError(
            "NQS gate unavailable: no ticker scored. "
            "Refusing to run a gated backtest on price signals alone."
        )
    return scores


def nqs_passes(ticker: str, nqs_scores: dict) -> bool:
    if nqs_scores is None:
        return True  # ungated variant: no NQS check at all
    score = nqs_scores.get(ticker)
    if score is None:
        return True
    return score >= NQS_MIN_THRESHOLD


# ── Layer 4: Position Construction ───────────────────────────────────────────

def run_backtest(equity_prices, defensive_prices, window, nqs_scores):
    """Run one momentum variant.

    nqs_scores=None means UNGATED (momentum + drawdown only — the honest
    variant). A dict means gated on today's NQS (in-sample — see the
    module docstring; the gate is lookahead, not a tradable result).
    Risk controls are unchanged: 15% trailing-drawdown stop, 100%
    take-profit, 0.05% slippage on rebalance days.
    """
    momentum_scores, asset_drawdowns = build_signals(equity_prices, window)
    equity_returns    = equity_prices.pct_change()
    defensive_returns = defensive_prices.pct_change()
    trading_days = equity_prices.index[window + 1:]

    strategy_returns = []
    equity_value     = 1.0
    equity_curve     = [equity_value]
    prev_basket      = []
    entry_prices     = {t: None for t in TICKERS}
    trade_log        = []

    for i, current_day in enumerate(trading_days):
        signal_day    = equity_prices.index[window + i]
        day_momentum  = momentum_scores.loc[signal_day]
        day_drawdowns = asset_drawdowns.loc[signal_day]

        basket = []
        for ticker in TICKERS:
            if pd.isna(day_momentum[ticker]):
                continue
            if day_momentum[ticker] <= 0:
                entry_prices[ticker] = None
                continue
            if day_drawdowns[ticker] <= -DRAWDOWN_LIMIT:
                entry_prices[ticker] = None
                continue
            if entry_prices[ticker] is None:
                entry_prices[ticker] = equity_prices.loc[signal_day, ticker]
            current_gain = (equity_prices.loc[signal_day, ticker] /
                            entry_prices[ticker]) - 1.0
            if current_gain >= TAKE_PROFIT:
                entry_prices[ticker] = None
                trade_log.append({"date": current_day, "ticker": ticker,
                                   "event": "take_profit", "gain_pct": round(current_gain * 100, 2)})
                continue
            if nqs_scores is not None and not nqs_passes(ticker, nqs_scores):
                continue
            basket.append(ticker)

        slippage_drag = SLIPPAGE if basket != prev_basket else 0.0

        if basket:
            weight       = 1.0 / len(basket)
            daily_return = (equity_returns.loc[current_day, basket].sum() * weight) - slippage_drag
        else:
            daily_return = defensive_returns.loc[current_day] - slippage_drag
            if prev_basket:
                trade_log.append({"date": current_day, "ticker": "SGOV",
                                   "event": "defensive_rotation", "gain_pct": None})

        strategy_returns.append(daily_return)
        equity_value *= (1 + daily_return)
        equity_curve.append(equity_value)
        prev_basket = basket

    returns_series = pd.Series(strategy_returns, index=trading_days)
    curve_series   = pd.Series(equity_curve, index=equity_prices.index[window:])
    return returns_series, curve_series, trade_log


# ── Layer 5: Metrics ──────────────────────────────────────────────────────────

def calc_metrics(returns: pd.Series, label: str) -> dict:
    if returns.empty:
        return {"label": label, "total_return": None, "ann_vol": None,
                "sharpe": None, "max_drawdown": None, "n_days": 0}

    total_return = (1 + returns).prod() - 1
    ann_vol      = returns.std() * np.sqrt(252)
    excess       = returns - (RISK_FREE_RATE / 252)
    sharpe       = (excess.mean() / returns.std() * np.sqrt(252)
                    if returns.std() > 0 else None)
    cum          = (1 + returns).cumprod()
    rolling_max  = cum.cummax()
    max_drawdown = ((cum - rolling_max) / rolling_max).min()

    return {
        "label":        label,
        "total_return": round(total_return * 100, 2),
        "ann_vol":      round(ann_vol * 100, 2),
        "sharpe":       round(sharpe, 3) if sharpe is not None else None,
        "max_drawdown": round(max_drawdown * 100, 2),
        "n_days":       len(returns),
    }


def build_benchmark_buy_and_hold(equity_prices, start_idx):
    """TRUE buy-and-hold benchmark: fixed shares, weights drift.

    Equal dollars in each ticker that has a valid price on the start
    day; the share counts then stay fixed, so weights drift with
    prices — that is what buy-and-hold means. A ticker that lists
    later never joins (it did not exist on the start day), and a
    ticker's mid-series price gap is carried forward at its last
    growth factor. Returns start on index[start_idx + 1], the same
    first trading day as a strategy with window=start_idx, so the
    comparison covers identical days.
    """
    start_day = equity_prices.index[start_idx]
    start_prices = equity_prices.loc[start_day].dropna()
    if start_prices.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    growth = equity_prices[start_prices.index].div(start_prices).ffill()
    bench_value = growth.mean(axis=1).loc[equity_prices.index[start_idx:]]
    bench_days = equity_prices.index[start_idx + 1:]
    bench_daily = bench_value.pct_change().loc[bench_days].fillna(0.0)
    return bench_daily, bench_value


def build_benchmark_equal_weight(equity_prices, start_idx):
    """Daily-rebalanced equal-weight benchmark (the ORIGINAL benchmark).

    Each day the return is the mean daily return of the tickers with a
    valid return that day — i.e. the portfolio is rebalanced back to
    equal weight EVERY day. This is NOT buy-and-hold: weights never
    drift, and a ticker that lists later joins at full equal weight
    the day its first return appears. Kept for continuity with
    earlier runs, labeled honestly. Returns start on
    index[start_idx + 1], the same first trading day as a strategy
    with window=start_idx.
    """
    returns = equity_prices.pct_change()
    bench_days = equity_prices.index[start_idx + 1:]
    bench_returns_list = []
    prev_count = None
    comp_log = []

    for day in bench_days:
        valid = returns.loc[day].dropna()
        valid_count = len(valid)
        if valid_count == 0:
            bench_returns_list.append(0.0)
            continue
        bench_returns_list.append(valid.sum() * (1.0 / valid_count))
        if valid_count != prev_count:
            comp_log.append(f"[BENCHMARK] {day.date()}: {valid_count} tickers active "
                            f"({', '.join(valid.index.tolist())})")
            prev_count = valid_count

    for entry in comp_log:
        print(entry)

    bench_daily = pd.Series(bench_returns_list, index=bench_days)
    bench_curve = pd.Series([1.0] + list((1 + bench_daily).cumprod()),
                            index=equity_prices.index[start_idx:])
    return bench_daily, bench_curve


# ── Chart ─────────────────────────────────────────────────────────────────────

def strategy_label(window: int, gated: bool) -> str:
    """Label for one momentum variant. The gated variant is always
    marked in-sample: its NQS gate is today's scores applied to the
    whole history (lookahead), not a tradable result."""
    if gated:
        return f"{window}-Day Momentum + NQS gate (in-sample)"
    return f"{window}-Day Momentum"


def plot_equity_curves(curves, output_path, title_suffix=""):
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(13, 7))
    colors = ["#00ffcc", "#ff9900", "#4fc3f7", "#ff6b6b", "#c792ea", "#aed581"]

    for idx, (label, curve) in enumerate(curves.items()):
        if curve is None or curve.empty:
            continue
        if "Buy & Hold" in label or "Equal-Weight" in label:
            ax.plot(curve.index, curve.values, label=label,
                    color="#888888", linestyle="--", linewidth=1.5, alpha=0.7)
        else:
            ax.plot(curve.index, curve.values, label=label,
                    color=colors[idx % len(colors)], linewidth=2)

    ax.set_title("Second Layer Capital — Nuclear Infrastructure\n"
                 "Momentum Strategy vs. Benchmarks"
                 + (f" ({title_suffix})" if title_suffix else ""),
                 fontsize=13, fontweight="bold", pad=15)
    ax.set_xlabel("Date", fontsize=11, labelpad=8)
    ax.set_ylabel("Growth of $1.00", fontsize=11, labelpad=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=30, ha="right")
    ax.grid(True, linestyle=":", alpha=0.35, color="#444444")
    ax.legend(loc="upper left", frameon=True,
              facecolor="#111111", edgecolor="#333333", fontsize=10)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="#000000")
    plt.close(fig)
    print(f"[CHART] Saved → {output_path}")


# ── Report ────────────────────────────────────────────────────────────────────

def print_report(metrics_list, run_info):
    """Print the backtest matrix.

    run_info: {"start_date", "end_date", "data_start", "data_end",
    "nqs_gate"} — the run window and gate status are part of the
    output so the numbers are reproducible: END_DATE is
    datetime.today(), so a rerun on another day covers another window.
    """
    print("\n" + "=" * 65)
    print("  SECOND LAYER CAPITAL — NUCLEAR BACKTEST MATRIX")
    print(f"  Run window: {run_info['start_date']} → {run_info['end_date']} "
          f"(data: {run_info['data_start']} → {run_info['data_end']})")
    print("  Risk controls: 15% stop-loss | 100% take-profit | 0.05% slippage")
    print(f"  NQS gate: {run_info['nqs_gate']}")
    print("=" * 65)
    print(f"  {'Strategy':<28} {'Return':>9} {'Ann.Vol':>9} {'Sharpe':>8} {'MaxDD':>9}")
    print("  " + "-" * 63)
    for m in metrics_list:
        if m["total_return"] is None:
            continue
        print(f"  {m['label']:<28} "
              f"{m['total_return']:>8.1f}% "
              f"{m['ann_vol']:>8.1f}% "
              f"{str(m['sharpe']):>8} "
              f"{m['max_drawdown']:>8.1f}%")
    print("=" * 65 + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def _run_one_variant(equity_prices, defensive_prices, window, label, nqs_scores,
                     all_metrics, equity_curves):
    print(f"\n[BACKTEST] Running {label}...")
    returns, curve, trade_log = run_backtest(
        equity_prices, defensive_prices, window, nqs_scores)
    metrics = calc_metrics(returns, label)
    all_metrics.append(metrics)
    equity_curves[label] = curve
    tp_events = [e for e in trade_log if e["event"] == "take_profit"]
    def_events = [e for e in trade_log if e["event"] == "defensive_rotation"]
    print(f"[BACKTEST] {label}: {metrics['total_return']}% total | "
          f"{metrics['ann_vol']}% vol | Sharpe {metrics['sharpe']} | "
          f"MaxDD {metrics['max_drawdown']}% | "
          f"{len(tp_events)} take-profits | {len(def_events)} defensive rotations")


def main():
    equity_prices, defensive_prices = load_prices()
    data_start = equity_prices.index[0].date()
    data_end = equity_prices.index[-1].date()

    # NQS is needed only for the gated (in-sample) variants. A total
    # load failure must not silently turn the gate off: banner loudly,
    # skip the gated variants, record it in the report, exit non-zero
    # after the honest (ungated + benchmark) numbers are printed.
    nqs_scores = None
    nqs_failed = False
    nqs_fail_reason = ""
    print("[NQS] Loading Nuclear Quality Scores...")
    try:
        nqs_scores = load_nqs_scores()
    except RuntimeError as e:
        nqs_failed = True
        nqs_fail_reason = str(e)
        print("!" * 65)
        print(f"!!! NQS GATE OFF: {e}")
        print("!!! Gated variants skipped — ungated momentum and benchmarks still run.")
        print("!" * 65)
    if nqs_scores is not None:
        scored = {t: v for t, v in nqs_scores.items() if v is not None}
        print("[NQS] Scored tickers: " + ", ".join(f"{t}={v}" for t, v in scored.items()))
        null_count = len(TICKERS) - len(scored)
        nqs_gate = (f"ACTIVE ({len(scored)}/{len(TICKERS)} scored, "
                    f"threshold {NQS_MIN_THRESHOLD})")
        if null_count:
            nqs_gate += (f" — {null_count} null, passing on price signals")
    else:
        nqs_gate = f"OFF — load failed ({nqs_fail_reason}); gated variants skipped"

    all_metrics = []
    equity_curves = {}

    for window in MOMENTUM_WINDOWS:
        # Ungated momentum: the honest variant (no lookahead gate).
        _run_one_variant(equity_prices, defensive_prices, window,
                         strategy_label(window, gated=False), None,
                         all_metrics, equity_curves)
        # Gated momentum: today's NQS applied to the whole history —
        # in-sample, labeled as such.
        if nqs_scores is not None:
            _run_one_variant(equity_prices, defensive_prices, window,
                             strategy_label(window, gated=True), nqs_scores,
                             all_metrics, equity_curves)

        # Benchmarks over the SAME trading days as this window's
        # strategies, so the comparison covers identical days.
        print(f"\n[BACKTEST] Building benchmarks for {window}-day window...")
        bh_returns, bh_curve = build_benchmark_buy_and_hold(equity_prices, window)
        bh_label = f"Benchmark (Buy & Hold) — {window}D"
        bh_metrics = calc_metrics(bh_returns, bh_label)
        all_metrics.append(bh_metrics)
        equity_curves[bh_label] = bh_curve
        print(f"[BACKTEST] {bh_label}: {bh_metrics['total_return']}% total | "
              f"Sharpe {bh_metrics['sharpe']} | MaxDD {bh_metrics['max_drawdown']}%")

        ew_returns, ew_curve = build_benchmark_equal_weight(equity_prices, window)
        ew_label = f"Equal-Weight (daily rebalanced) — {window}D"
        ew_metrics = calc_metrics(ew_returns, ew_label)
        all_metrics.append(ew_metrics)
        equity_curves[ew_label] = ew_curve
        print(f"[BACKTEST] {ew_label}: {ew_metrics['total_return']}% total | "
              f"Sharpe {ew_metrics['sharpe']} | MaxDD {ew_metrics['max_drawdown']}%")

    run_info = {"start_date": START_DATE, "end_date": END_DATE,
                "data_start": str(data_start), "data_end": str(data_end),
                "nqs_gate": nqs_gate}
    print_report(all_metrics, run_info)

    # Chart: the three honest momentum curves plus the 60-day window's
    # benchmarks (the live strategy's window). The full matrix is in
    # the printed report; twelve curves on one chart is unreadable.
    chart_curves = {}
    for window in MOMENTUM_WINDOWS:
        label = strategy_label(window, gated=False)
        chart_curves[label] = equity_curves[label]
    chart_curves[f"Benchmark (Buy & Hold) — 60D"] = equity_curves[
        "Benchmark (Buy & Hold) — 60D"]
    chart_curves[f"Equal-Weight (daily rebalanced) — 60D"] = equity_curves[
        "Equal-Weight (daily rebalanced) — 60D"]
    plot_equity_curves(chart_curves, CHART_PATH,
                       title_suffix=f"{START_DATE} → {END_DATE}")

    return 2 if nqs_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
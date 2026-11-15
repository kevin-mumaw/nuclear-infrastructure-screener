"""
Second Layer Capital — Overnight Volatility Gap-Risk Warner
Scans active asset tracking domains to identify pre-market price dislocations.

The overnight gap for a ticker is today's open vs the prior close:
    gap% = (today's open - prior close) / prior close * 100
That is the price move that happened while the market was closed —
the dislocation a holder actually wakes up to. (An earlier version of
this module compared close-to-close, which is just the day-over-day
move, not an overnight gap.)
"""

import yfinance as yf
from config.universe import UNIVERSE


def overnight_gap_pct(prev_close: float, today_open: float) -> float:
    """Overnight gap in percent: today's open vs the prior close."""
    return ((today_open - prev_close) / prev_close) * 100


def gap_from_history(hist):
    """Extract (prev_close, today_open, gap_pct) from a yfinance history frame.

    Returns None when the frame has fewer than two rows or either price
    is missing/NaN (e.g. a holiday row) — a data gap, not a zero gap.
    """
    if hist is None or len(hist) < 2:
        return None
    prev_close = hist["Close"].iloc[-2]
    today_open = hist["Open"].iloc[-1]
    try:
        prev_close = float(prev_close)
        today_open = float(today_open)
    except (TypeError, ValueError):
        return None
    if prev_close == 0 or prev_close != prev_close or today_open != today_open:
        return None
    return prev_close, today_open, overnight_gap_pct(prev_close, today_open)


def gap_status(gap_pct: float, threshold_pct: float) -> str:
    """Risk label for a measured gap. Pure function, for testing."""
    if abs(gap_pct) >= threshold_pct:
        return "🚨 BREACH (Gap Down)" if gap_pct < 0 else "🚀 EXPANSION (Gap Up)"
    return "🟢 NOMINAL"


def scan_overnight_gaps(threshold_pct=3.0):
    print("Initializing Systemic Overnight Volatility Scan...")

    # Extract all active tracking tickers out of your universe categories
    all_tickers = []
    for domain in UNIVERSE.values():
        all_tickers.extend(domain["tickers"])

    print(f"Scanning tracking universe across {len(all_tickers)} key industrial bottleneck nodes...")
    print(f"Risk Trigger Threshold set at: ±{threshold_pct}% overnight price dislocation.\n")

    print(f"================================================================")
    print(f"       SECOND LAYER CAPITAL — VOLATILITY OVERNIGHT TRACKER      ")
    print(f"================================================================")
    print(f"{'TICKER':<8}{'PREV CLOSE':<12}{'TODAY OPEN':<12}{'GAP DELTA':<12}{'RISK STATUS'}")
    print("-" * 64)

    gap_alerts_found = 0

    for ticker in all_tickers:
        try:
            asset = yf.Ticker(ticker)
            # Five days of history: two rows are the minimum (prior close
            # + today's open), the extra days cover weekends/holidays so
            # the last two rows are still the latest trading days.
            hist = asset.history(period="5d")

            result = gap_from_history(hist)
            if result is None:
                print(f"{ticker:<8}Insufficient price history to measure an overnight gap.")
                continue

            prev_close, today_open, gap_pct = result

            # Check if the overnight volatility breach passes our threshold filter
            if abs(gap_pct) >= threshold_pct:
                gap_alerts_found += 1
            status = gap_status(gap_pct, threshold_pct)

            print(f"{ticker:<8}${prev_close:<11.2f}${today_open:<11.2f}{gap_pct:+.2f}%      {status}")

        except Exception as e:
            # A failed fetch is reported with its error, not mistaken for
            # a quiet ticker.
            print(f"{ticker:<8}Failed to fetch price data ({e}).")

    print(f"================================================================")
    print(f"🚨 SCAN COMPLETE: Identified {gap_alerts_found} high-volatility price gap events.")
    print(f"================================================================")

if __name__ == "__main__":
    # Execute scan with a 3.0% structural volatility boundary
    scan_overnight_gaps(threshold_pct=3.0)

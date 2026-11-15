"""
Nuclear Infrastructure Screener — Earnings Cycle Alert
Second Layer Capital

Standalone script. Run independently from backtester.py.

    python earnings_alert.py

What it does:
  1. Pulls upcoming earnings dates from yfinance for the six tickers that
     require manual backlog/book-to-bill updates each quarter:
     BWXT, GEV, FLS, IR, J, FLR
  2. Compares each earnings date against today's date.
  3. Prints a tiered alert for any ticker whose earnings falls within the
     next 14 days (ACTION REQUIRED) or 30 days (UPCOMING).
  4. Reads manual_overrides.json and flags any ticker whose last_updated
     date is older than 90 days, regardless of upcoming earnings.
  5. Prints the exact manual_overrides.json fields you need to update for
     each flagged ticker, so there is no guessing about what to change.

Run from inside your virtual environment:
  .venv\\Scripts\\activate
  python earnings_alert.py
"""

import json
import os
import pandas as pd
from datetime import datetime, timedelta

import yfinance as yf

BACKLOG_TICKERS  = ["BWXT", "GEV", "FLS", "IR", "J", "FLR"]
ALERT_WINDOW     = 14
UPCOMING_WINDOW  = 30
STALE_THRESHOLD  = 90

OVERRIDES_PATH = os.path.join(
    os.path.dirname(__file__), "config", "manual_overrides.json"
)

DATA_SOURCES = {
    "BWXT": "10-Q, MD&A section, 'Backlog' subsection",
    "GEV":  "Quarterly earnings supplement PDF, 'Orders and Backlog' table",
    "FLS":  "10-Q, MD&A section, 'Bookings and Backlog' subsection",
    "IR":   "10-Q, MD&A section, 'Orders' metrics (no consolidated backlog — BTB only, leave backlog_growth_yoy as null)",
    "J":    "10-Q, 'Backlog' section near front of MD&A",
    "FLR":  "10-Q, MD&A section, 'New Awards and Backlog' subsection",
}


def load_overrides() -> dict:
    if not os.path.exists(OVERRIDES_PATH):
        return {}
    with open(OVERRIDES_PATH) as f:
        return json.load(f)


def parse_calendar_earnings_date(cal, today):
    """Parse the next earnings date out of a yfinance calendar payload.

    Returns the earliest date >= today, or None when the payload has no
    usable future earnings date. Never raises on a malformed payload:
    an unreadable calendar is a "no date" outcome, not a crash.

    Shapes handled (yfinance changed shape between versions):
    - dict (yfinance >= 1.x): {"Earnings Date": [date, ...]} — the value
      is a list, sometimes a range of two dates; element [0] is the date
      Yahoo knows. A scalar is accepted defensively.
    - DataFrame (yfinance <= 0.2.x): an "Earnings Date" row, values
      parsed as timestamps. Duck-typed so this module does not need
      to know which shape it got.
    """
    if cal is None:
        return None

    if isinstance(cal, dict):
        values = cal.get("Earnings Date")
        if values is None:
            return None
        if not isinstance(values, (list, tuple)):
            values = [values]
        dates = []
        for val in values:
            try:
                d = pd.Timestamp(val).date()
                if d >= today:
                    dates.append(d)
            except Exception:
                continue
        return min(dates) if dates else None

    # DataFrame shape — duck-typed.
    if hasattr(cal, "empty") and hasattr(cal, "loc"):
        if cal.empty:
            return None
        if "Earnings Date" in cal.index:
            raw = cal.loc["Earnings Date"]
            # .values may be 2-D if the index repeats; flatten so each
            # entry is a single value.
            values = raw.values.flatten() if hasattr(raw, "values") else [raw]
            dates = []
            for val in values:
                try:
                    d = pd.Timestamp(val).date()
                    if d >= today:
                        dates.append(d)
                except Exception:
                    continue
            return min(dates) if dates else None
        return None

    return None


def get_earnings_date(ticker: str):
    try:
        t     = yf.Ticker(ticker)
        today = datetime.today().date()

        # Attempt 1: info dict next earnings date
        info = t.info or {}
        ts   = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
        if ts:
            d = datetime.fromtimestamp(ts).date()
            if d >= today:
                return datetime.combine(d, datetime.min.time())

        # Attempt 2: earnings_dates DataFrame
        try:
            ed = t.earnings_dates
            if ed is not None and not ed.empty:
                future = [d.date() for d in ed.index if d.date() >= today]
                if future:
                    return datetime.combine(min(future), datetime.min.time())
        except Exception:
            pass

        # Attempt 3: calendar attribute — dict in yfinance >= 1.x,
        # DataFrame in older versions. parse_calendar_earnings_date
        # handles both shapes and never raises on a bad payload.
        try:
            d = parse_calendar_earnings_date(t.calendar, today)
            if d is not None:
                return datetime.combine(d, datetime.min.time())
        except Exception:
            pass

    except Exception:
        pass
    return None


def days_until(target: datetime) -> int:
    return (target.date() - datetime.today().date()).days


def days_since(date_str: str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return (datetime.today() - d).days
    except Exception:
        return None


def print_divider(char="-", width=65):
    print(char * width)


def print_header():
    print()
    print_divider("=")
    print("  SECOND LAYER CAPITAL -- EARNINGS CYCLE ALERT")
    print(f"  Nuclear Infrastructure Screener  |  {datetime.today().strftime('%Y-%m-%d')}")
    print(f"  Tracking: {', '.join(BACKLOG_TICKERS)}")
    print_divider("=")
    print()


def print_alert(ticker, earnings_date, days, overrides):
    entry        = overrides.get(ticker, {})
    last_updated = entry.get("last_updated", "never")
    btb          = entry.get("book_to_bill", "null")
    growth       = entry.get("backlog_growth_yoy", "null")
    source       = DATA_SOURCES.get(ticker, "see company IR page")
    urgency      = "ACTION REQUIRED" if days <= ALERT_WINDOW else "UPCOMING"
    marker       = ">>>" if days <= ALERT_WINDOW else " ! "

    print(f"  [{marker}]  {ticker}  --  {urgency}")
    print(f"         Earnings date : {earnings_date.strftime('%Y-%m-%d')}  ({days} days away)")
    print(f"         Last updated  : {last_updated}")
    print(f"         Current BTB   : {btb}")
    print(f"         Current growth: {growth}")
    print(f"         Data source   : {source}")
    print()
    print(f"         Fields to update in config/manual_overrides.json:")
    print(f'           "backlog_growth_yoy": <decimal, e.g. 0.25 for +25%>')
    print(f'           "book_to_bill": <decimal, e.g. 1.35>')
    print(f'           "last_updated": "{datetime.today().strftime("%Y-%m-%d")}"')
    print(f'           "source": "<10-Q quarter and key figures>"')
    print()
    print_divider()
    print()


def print_stale_alert(ticker, days_old, overrides):
    entry        = overrides.get(ticker, {})
    last_updated = entry.get("last_updated", "never")
    source       = DATA_SOURCES.get(ticker, "see company IR page")

    print(f"  [AGE]  {ticker}  --  STALE DATA WARNING")
    print(f"         Last updated  : {last_updated}  ({days_old} days ago)")
    print(f"         Threshold     : {STALE_THRESHOLD} days")
    print(f"         Data source   : {source}")
    print(f"         Action        : Check {ticker} IR page for recent 10-Q filing.")
    print()
    print_divider()
    print()


def print_no_date(ticker, overrides):
    entry        = overrides.get(ticker, {})
    last_updated = entry.get("last_updated", "never")

    print(f"  [ ? ]  {ticker}  --  NO EARNINGS DATE FOUND")
    print(f"         yfinance returned no upcoming earnings date for {ticker}.")
    print(f"         Last updated: {last_updated}")
    print(f"         Action: Check {ticker} investor relations page manually.")
    print()
    print_divider()
    print()


def main():
    overrides = load_overrides()
    today     = datetime.today()

    print_header()

    action_required = []
    upcoming        = []
    no_date         = []
    stale           = []
    clean           = []

    print("  Pulling earnings dates from yfinance...")
    print()

    for ticker in BACKLOG_TICKERS:
        earnings_date = get_earnings_date(ticker)

        if earnings_date is None:
            no_date.append(ticker)
        else:
            days = days_until(earnings_date)
            if days <= ALERT_WINDOW:
                action_required.append((ticker, earnings_date, days))
            elif days <= UPCOMING_WINDOW:
                upcoming.append((ticker, earnings_date, days))
            else:
                clean.append((ticker, earnings_date, days))

        entry        = overrides.get(ticker, {})
        last_updated = entry.get("last_updated")
        if last_updated:
            age = days_since(last_updated)
            if age and age > STALE_THRESHOLD:
                stale.append((ticker, age))
        else:
            stale.append((ticker, None))

    if action_required:
        print(f"  ACTION REQUIRED -- {len(action_required)} ticker(s) reporting within {ALERT_WINDOW} days")
        print_divider()
        print()
        for ticker, earnings_date, days in action_required:
            print_alert(ticker, earnings_date, days, overrides)

    if upcoming:
        print(f"  UPCOMING -- {len(upcoming)} ticker(s) reporting within {UPCOMING_WINDOW} days")
        print_divider()
        print()
        for ticker, earnings_date, days in upcoming:
            print_alert(ticker, earnings_date, days, overrides)

    if stale:
        print(f"  STALE DATA -- {len(stale)} ticker(s) not updated in {STALE_THRESHOLD}+ days")
        print_divider()
        print()
        for ticker, age in stale:
            age_display = age if age is not None else "unknown"
            print_stale_alert(ticker, age_display, overrides)

    if no_date:
        print(f"  NO DATE FOUND -- {len(no_date)} ticker(s) returned no upcoming earnings date")
        print_divider()
        print()
        for ticker in no_date:
            print_no_date(ticker, overrides)

    if clean:
        print("  ALL CLEAR -- tickers with earnings more than 30 days away:")
        for ticker, earnings_date, days in clean:
            entry        = overrides.get(ticker, {})
            last_updated = entry.get("last_updated", "never")
            print(f"    {ticker:<6}  earnings {earnings_date.strftime('%Y-%m-%d')}  ({days} days)  last updated {last_updated}")
        print()

    print_divider("=")
    print(f"  SUMMARY  |  {datetime.today().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Action required : {len(action_required)}")
    print(f"  Upcoming (30d)  : {len(upcoming)}")
    print(f"  Stale data      : {len(stale)}")
    print(f"  No date found   : {len(no_date)}")
    print(f"  Clean           : {len(clean)}")
    print_divider("=")
    print()

    if action_required or stale:
        print("  Next step: update config/manual_overrides.json then run:")
        print("    python backtester.py")
        print("  Then commit:")
        print('    git add config/manual_overrides.json')
        print('    git commit -m "Data: Q[X] [YEAR] backlog update"')
        print('    git push origin master')
        print()


if __name__ == "__main__":
    main()
"""
Nuclear Infrastructure Screener — Weekly Live Signal
Second Layer Capital

Run manually at your desk before market open, any day of the week.

    python live_signal.py

Prints a complete order sheet. You place the orders manually in Schwab.
"""

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

ACCOUNT_CAPITAL = 800.00
MIN_POSITIONS   = 4
MAX_POSITIONS   = 6
MOMENTUM_WINDOW = 60
DRAWDOWN_LIMIT  = 0.15
NQS_GATE        = 40
LIMIT_OFFSET    = 0.005
DEFENSIVE       = "USFR"

TICKERS = [
    "CCJ", "UEC", "DNN", "LEU",
    "BWXT", "GEV", "FLS", "IR",
    "OKLO", "SMR",
    "CEG", "VST", "TLN",
    "J", "FLR",
]

IPO_FLOORS = {
    "OKLO": "2024-05-10",
    "GEV":  "2024-04-02",
    "TLN":  "2023-05-17",
}

OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "config", "manual_overrides.json")
STATE_PATH     = os.path.join(os.path.dirname(__file__), "signal_state.json")
LOOKBACK_DAYS  = 120


def load_prices():
    all_tickers = TICKERS + [DEFENSIVE]
    print(f"  [DATA] Pulling {LOOKBACK_DAYS}-day price history...")
    raw = yf.download(
        all_tickers,
        period=f"{LOOKBACK_DAYS}d",
        auto_adjust=True,
        progress=False,
    )["Close"]
    raw = raw.ffill().dropna(how="all")
    eq  = raw[TICKERS].copy()
    for ticker, floor in IPO_FLOORS.items():
        if ticker in eq.columns:
            eq.loc[eq.index < pd.Timestamp(floor), ticker] = np.nan
    return eq, raw[DEFENSIVE]


def load_nqs_scores():
    scores = {}
    try:
        from scoring.nqs_scorer import calculate_nqs
        overrides = {}
        if os.path.exists(OVERRIDES_PATH):
            with open(OVERRIDES_PATH) as f:
                overrides = json.load(f)
        for ticker in TICKERS:
            result = calculate_nqs(ticker, overrides)
            scores[ticker] = result.get("nqs")
    except Exception as e:
        print(f"  [NQS] Warning: could not load NQS scores ({e})")
    return scores


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"last_basket": [], "last_run": None}


def save_state(basket):
    state = {"last_basket": basket, "last_run": datetime.today().strftime("%Y-%m-%d")}
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def build_signal(equity_prices, nqs_scores):
    if len(equity_prices) < MOMENTUM_WINDOW + 1:
        print(f"  [SIGNAL] Not enough price history.")
        return []

    qualifying = []
    for ticker in TICKERS:
        col = equity_prices[ticker]
        if col.isna().all():
            continue
        current_price  = col.iloc[-1]
        lookback_price = col.iloc[-(MOMENTUM_WINDOW + 1)]
        if pd.isna(current_price) or pd.isna(lookback_price):
            continue
        momentum = (current_price / lookback_price) - 1.0
        if momentum <= 0:
            continue
        peak     = col.dropna().max()
        drawdown = (current_price - peak) / peak
        if drawdown <= -DRAWDOWN_LIMIT:
            continue
        nqs = nqs_scores.get(ticker)
        if nqs is not None and nqs < NQS_GATE:
            continue
        qualifying.append({
            "ticker":   ticker,
            "nqs":      nqs if nqs is not None else "--",
            "momentum": round(momentum * 100, 1),
            "drawdown": round(drawdown * 100, 1),
            "price":    round(current_price, 2),
        })

    qualifying.sort(key=lambda x: (x["nqs"] == "--", -(x["nqs"] if x["nqs"] != "--" else 0)))
    return qualifying[:MAX_POSITIONS]


def build_order_sheet(basket, defensive_price):
    orders   = []
    n_equity = len(basket)
    n_def    = max(0, MIN_POSITIONS - n_equity)
    n_total  = n_equity + n_def
    pos_size = ACCOUNT_CAPITAL / n_total if n_total > 0 else ACCOUNT_CAPITAL

    for item in basket:
        limit_price = round(item["price"] * (1 + LIMIT_OFFSET), 2)
        shares      = int(pos_size / limit_price)
        orders.append({
            "ticker":      item["ticker"],
            "nqs":         item["nqs"],
            "momentum":    item["momentum"],
            "drawdown":    item["drawdown"],
            "last_close":  item["price"],
            "limit_price": limit_price,
            "shares":      shares,
            "actual_cost": round(shares * limit_price, 2),
            "type":        "EQUITY",
        })

    if n_def > 0:
        defensive_allocation = pos_size * n_def
        limit_price = round(defensive_price * (1 + LIMIT_OFFSET), 2)
        shares      = int(defensive_allocation / limit_price)
        orders.append({
            "ticker":      DEFENSIVE,
            "nqs":         "--",
            "momentum":    "--",
            "drawdown":    "--",
            "last_close":  round(defensive_price, 2),
            "limit_price": limit_price,
            "shares":      shares,
            "actual_cost": round(shares * limit_price, 2),
            "type":        "DEFENSIVE",
        })

    return orders


def get_changes(current_orders, last_basket):
    current_tickers = [o["ticker"] for o in current_orders]
    added   = [t for t in current_tickers if t not in last_basket]
    removed = [t for t in last_basket     if t not in current_tickers]
    return added, removed


def print_divider(char="-", width=68):
    print(char * width)


def print_report(orders, added, removed, state):
    today    = datetime.today().strftime("%Y-%m-%d %H:%M")
    last_run = state.get("last_run", "never")
    n_eq     = sum(1 for o in orders if o["type"] == "EQUITY")
    n_def    = sum(1 for o in orders if o["type"] == "DEFENSIVE")

    print()
    print_divider("=")
    print("  SECOND LAYER CAPITAL -- NUCLEAR INFRASTRUCTURE")
    print("  Weekly Live Signal  |  60-Day Momentum  |  NQS Gate >= 40")
    print(f"  Generated : {today}")
    print(f"  Prior run : {last_run}")
    print(f"  Capital   : ${ACCOUNT_CAPITAL:,.2f}  |  {n_eq} equity + {n_def} defensive")
    print_divider("=")
    print()

    if added or removed:
        print("  CHANGES FROM PRIOR WEEK:")
        for t in added:
            print(f"    + {t}  (entering basket)")
        for t in removed:
            print(f"    - {t}  (exiting basket -- close this position)")
        print()
    elif last_run != "never":
        print("  No changes from prior week. Basket is unchanged.")
        print()

    print("  ORDER SHEET -- Enter in Schwab before market open")
    print(f"  Order type: BUY LIMIT  |  Duration: DAY  |  Offset: +{LIMIT_OFFSET*100:.1f}% above prior close")
    print()
    print(f"  {'TICKER':<8} {'TYPE':<10} {'NQS':<6} {'MOM%':<8} {'DD%':<8} {'CLOSE':<8} {'LIMIT':<8} {'SHARES':<8} {'COST'}")
    print_divider()

    total_deployed = 0
    for o in orders:
        nqs_str = str(o["nqs"])
        mom_str = f"{o['momentum']}%" if o["momentum"] != "--" else "--"
        dd_str  = f"{o['drawdown']}%" if o["drawdown"] != "--" else "--"
        print(f"  {o['ticker']:<8} {o['type']:<10} {nqs_str:<6} {mom_str:<8} {dd_str:<8} ${o['last_close']:<7} ${o['limit_price']:<7} {o['shares']:<8} ${o['actual_cost']}")
        total_deployed += o["actual_cost"]

    print_divider()
    cash_remaining = round(ACCOUNT_CAPITAL - total_deployed, 2)
    print(f"  Total deployed : ${total_deployed:,.2f}")
    print(f"  Cash remaining : ${cash_remaining:,.2f}")
    print()

    if removed:
        print("  SELL INSTRUCTIONS -- Close these before placing new orders:")
        for t in removed:
            print(f"    SELL ALL shares of {t} -- MARKET ORDER at open")
        print()

    print("  REMINDERS:")
    print(f"    Stop-loss   : Sell if any position drops 15% from your entry price.")
    print(f"    Take-profit : Sell if any position doubles from your entry price.")
    print()
    print_divider("=")
    print()


def main():
    print()
    print_divider("=")
    print("  NUCLEAR INFRASTRUCTURE SCREENER -- LIVE SIGNAL")
    print(f"  {datetime.today().strftime('%Y-%m-%d %H:%M')}")
    print_divider("=")
    print()

    equity_prices, defensive_prices = load_prices()
    defensive_last_close = defensive_prices.iloc[-1]

    print(f"  [DATA] {len(equity_prices)} trading days loaded. Latest close: {equity_prices.index[-1].strftime('%Y-%m-%d')}")

    print("  [NQS]  Loading Nuclear Quality Scores...")
    nqs_scores = load_nqs_scores()
    scored = {t: v for t, v in nqs_scores.items() if v is not None}
    print(f"  [NQS]  {len(scored)}/{len(TICKERS)} tickers scored. Gate >= {NQS_GATE}.")

    print(f"  [SIG]  Running {MOMENTUM_WINDOW}-day momentum filter + NQS gate...")
    basket = build_signal(equity_prices, nqs_scores)

    if not basket:
        print("  [SIG]  No tickers passed all filters. Full allocation to USFR.")
    else:
        print(f"  [SIG]  {len(basket)} tickers qualify: {', '.join(b['ticker'] for b in basket)}")

    orders = build_order_sheet(basket, defensive_last_close)

    state          = load_state()
    last_basket    = state.get("last_basket", [])
    added, removed = get_changes(orders, last_basket)

    print_report(orders, added, removed, state)

    save_state([o["ticker"] for o in orders])
    print(f"  Signal state saved to signal_state.json")
    print()


if __name__ == "__main__":
    main()
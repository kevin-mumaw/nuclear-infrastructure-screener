"""
Pulls automatable fundamental data for NQS scoring via yfinance.

Covers two of the three NQS buckets:
  - Balance Sheet Runway  (Net Debt/EBITDA for established names, cash-runway
    quarters for pre-revenue SMRs)
  - Margin Expansion      (gross margin YoY trend, ROIC)

Does NOT cover Backlog Momentum (12-mo backlog growth, book-to-bill) -- that
data is not in any free API. It lives in manual_overrides.json instead.

The module also provides the allocator's technical filter
(fetch_technical_signals): RSI-14 (Wilder's smoothing), the 50-day simple
moving average, and the latest close price.
"""

import yfinance as yf


def fetch_balance_sheet_runway(ticker: str, is_pre_revenue: bool = False) -> dict:
    t = yf.Ticker(ticker)
    info = t.info or {}

    if is_pre_revenue:
        operating_cf = None
        try:
            cf = t.cashflow
            if "Operating Cash Flow" in cf.index:
                operating_cf = cf.loc["Operating Cash Flow"].iloc[0]
            elif "Total Cash From Operating Activities" in cf.index:
                operating_cf = cf.loc["Total Cash From Operating Activities"].iloc[0]
        except Exception:
            operating_cf = None

        cash = info.get("totalCash")
        runway_quarters = None
        if cash and operating_cf and operating_cf < 0:
            quarterly_burn = abs(operating_cf) / 4
            if quarterly_burn:
                runway_quarters = cash / quarterly_burn

        return {
            "metric_type": "cash_runway_quarters",
            "value": runway_quarters,
            "raw": {"cash": cash, "annual_operating_cf": operating_cf},
        }

    total_debt = info.get("totalDebt")
    total_cash = info.get("totalCash")
    ebitda = info.get("ebitda")
    net_debt_to_ebitda = None
    if total_debt is not None and total_cash is not None and ebitda:
        net_debt = total_debt - total_cash
        # NOTE: a negative EBITDA yields a negative ratio, which is NOT a
        # low-leverage signal -- the scorer (score_balance_sheet_runway)
        # scores it 0. Do not "fix" the sign here; the raw ebitda below
        # is what lets the scorer tell net cash apart from losses.
        net_debt_to_ebitda = net_debt / ebitda if ebitda != 0 else None

    return {
        "metric_type": "net_debt_to_ebitda",
        "value": net_debt_to_ebitda,
        "raw": {"total_debt": total_debt, "total_cash": total_cash, "ebitda": ebitda},
    }


def fetch_margin_expansion(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info or {}

    gross_margin_current = info.get("grossMargins")
    gross_margin_trend = None
    try:
        fin = t.financials
        if "Total Revenue" in fin.index and "Gross Profit" in fin.index:
            revenue = fin.loc["Total Revenue"]
            gross_profit = fin.loc["Gross Profit"]
            margins = (gross_profit / revenue).dropna()
            if len(margins) >= 2:
                gross_margin_trend = float(margins.iloc[0] - margins.iloc[1])
    except Exception:
        pass

    roic = None
    try:
        fin = t.financials
        bs = t.balance_sheet
        op_income = None
        for label in ("Operating Income", "EBIT"):
            if label in fin.index:
                op_income = fin.loc[label].iloc[0]
                break

        total_debt = bs.loc["Total Debt"].iloc[0] if "Total Debt" in bs.index else None
        equity = None
        for label in ("Stockholders Equity", "Total Stockholder Equity"):
            if label in bs.index:
                equity = bs.loc[label].iloc[0]
                break
        cash = None
        for label in ("Cash And Cash Equivalents", "Cash"):
            if label in bs.index:
                cash = bs.loc[label].iloc[0]
                break

        tax_rate = info.get("effectiveTaxRate") or 0.21
        if op_income is not None and total_debt is not None and equity is not None and cash is not None:
            nopat = op_income * (1 - tax_rate)
            invested_capital = total_debt + equity - cash
            if invested_capital:
                roic = nopat / invested_capital
    except Exception:
        pass

    return {
        "gross_margin_current": gross_margin_current,
        "gross_margin_trend": gross_margin_trend,
        "roic": roic,
    }


# -- Technical signals (allocator.py's RSI / 50-SMA filter) --------------------
#
# fetch_technical_signals was imported by allocator.py but never written.
# It lives here now. RSI-14 uses Wilder's smoothing (the standard): the first
# average gain/loss is the simple mean of the first 14 changes, then each
# step is avg = (prev_avg * 13 + current) / 14.

RSI_PERIOD = 14
SMA_PERIOD = 50
TECHNICAL_HISTORY_PERIOD = "6mo"  # ~126 trading days: warm-up for both signals
MIN_CLOSES = SMA_PERIOD + 1  # 50 closes for the SMA, plus the current close

_NONE_SIGNALS = {"close_price": None, "rsi_14": None, "above_50_sma": None}


def _wilder_rsi(closes, period=RSI_PERIOD):
    """Wilder's RSI over closes, oldest first. Needs period + 1 values.

    Returns None when there are too few closes. When there are no down-moves
    at all the RSI is 100.0 if there was any up-move, else 50.0 (flat prices
    are neutral, not overbought).
    """
    values = [float(c) for c in closes]
    if len(values) < period + 1:
        return None

    gains = []
    losses = []
    for prev, cur in zip(values, values[1:]):
        change = cur - prev
        gains.append(change if change > 0 else 0.0)
        losses.append(-change if change < 0 else 0.0)

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _technical_signals_from_closes(closes) -> dict:
    """Pure computation from daily closes (oldest first).

    Returns {"close_price", "rsi_14", "above_50_sma"}. When fewer than
    MIN_CLOSES closes are available all three are None -- the caller treats
    that as no usable price data.
    """
    try:
        import pandas as pd

        if isinstance(closes, pd.Series):
            values = closes.dropna().astype(float).tolist()
        else:
            values = [float(c) for c in closes]
    except (TypeError, ValueError):
        return dict(_NONE_SIGNALS)

    if len(values) < MIN_CLOSES:
        return dict(_NONE_SIGNALS)

    close_price = values[-1]
    sma_50 = sum(values[-SMA_PERIOD:]) / SMA_PERIOD
    return {
        "close_price": close_price,
        "rsi_14": _wilder_rsi(values),
        "above_50_sma": close_price > sma_50,
    }


def fetch_technical_signals(ticker: str) -> dict:
    """RSI-14, 50-day SMA status, and latest close for one ticker.

    Pulls ~6 months of daily closes via yfinance. On any fetch failure, or
    when too few closes come back, returns all Nones instead of raising --
    allocator.py prints DATA ERROR for that ticker and moves on.
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=TECHNICAL_HISTORY_PERIOD, interval="1d")
        if hist is None or hist.empty or "Close" not in hist.columns:
            return dict(_NONE_SIGNALS)
        closes = hist["Close"].dropna()
        if len(closes) < MIN_CLOSES:
            return dict(_NONE_SIGNALS)
        return _technical_signals_from_closes(closes)
    except Exception:
        return dict(_NONE_SIGNALS)
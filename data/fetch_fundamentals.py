"""
Pulls automatable fundamental data for NQS scoring via yfinance.

Covers two of the three NQS buckets:
  - Balance Sheet Runway  (Net Debt/EBITDA for established names, cash-runway
    quarters for pre-revenue SMRs)
  - Margin Expansion      (gross margin YoY trend, ROIC)

Does NOT cover Backlog Momentum (12-mo backlog growth, book-to-bill) — that
data isn't in any free API. It lives in manual_overrides.json instead. See
scoring/nqs_scorer.py for how the buckets combine.
"""

import yfinance as yf


def fetch_balance_sheet_runway(ticker: str, is_pre_revenue: bool = False) -> dict:
    """
    Returns either a net_debt_to_ebitda figure (established companies) or a
    cash_runway_quarters figure (pre-revenue SMRs), depending on stage.
    """
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
        net_debt_to_ebitda = net_debt / ebitda if ebitda != 0 else None

    return {
        "metric_type": "net_debt_to_ebitda",
        "value": net_debt_to_ebitda,
        "raw": {"total_debt": total_debt, "total_cash": total_cash, "ebitda": ebitda},
    }


def fetch_margin_expansion(ticker: str) -> dict:
    """
    Returns current gross margin, YoY gross margin trend, and an ROIC estimate.
    All three can come back as None for thin/early-stage names — that's
    informative, not a bug, and the scorer should treat None as "no points,"
    not "zero points."
    """
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
                # yfinance columns are most-recent-first
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

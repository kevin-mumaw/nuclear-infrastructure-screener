"""
Pulls automatable fundamental and technical data for NQS scoring via yfinance.
"""

import yfinance as yf
import pandas as pd

def fetch_technical_signals(ticker: str) -> dict:
    """
    Calculates the 14-day RSI and evaluates if the current price 
    is trading above its 50-day Simple Moving Average (SMA).
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="6mo")
        if hist.empty or len(hist) < 50:
            return {"rsi_14": None, "above_50_sma": False, "close_price": 0.0}

        close_prices = hist['Close']
        last_price = float(close_prices.iloc[-1])

        # 1. Calculate 50-day Simple Moving Average
        sma_50 = float(close_prices.rolling(window=50).mean().iloc[-1])
        above_50_sma = last_price > sma_50

        # 2. Calculate 14-day RSI
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        rs = gain / loss
        rsi_14 = float(100 - (100 / (1 + rs)).iloc[-1])

        return {
            "rsi_14": round(rsi_14, 2),
            "above_50_sma": above_50_sma,
            "close_price": round(last_price, 2)
        }
    except Exception:
        return {"rsi_14": None, "above_50_sma": False, "close_price": 0.0}


def fetch_balance_sheet_runway(ticker: str, is_pre_revenue: bool = False) -> dict:
    """
    Returns either a net_debt_to_ebitda figure or a cash_runway_quarters figure.
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

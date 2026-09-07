"""
Nuclear Quality Score (NQS) scoring engine.

Three buckets, each scored 0-10, averaged across whichever buckets actually
apply to a given ticker's domain, then scaled to a 0-100 NQS for comparability
across domains with different numbers of applicable buckets.

  1. Backlog Momentum     -- components_grid and epc domains only (manual data)
  2. Balance Sheet Runway -- all domains (Net Debt/EBITDA or cash-runway path)
  3. Margin Expansion     -- all domains except smr_pureplay (pre-revenue)

Domain-Aware Threshold Architecture:
  Universal thresholds are NOT lowered to accommodate capital-intensive names.
  Instead, each domain carries its own threshold set appropriate to its
  operational profile.

  Domain            Net Debt/EBITDA   ROIC      Gross Margin   Primary Risk
  fuel_cycle        Universal         Universal  Universal      Structural Demand
  components_grid   4.0x              8.0%       18.0%          Backlog Trajectory
  smr_pureplay      N/A               N/A        N/A            Cash Runway / Burn
  utilities         5.0x              Universal  Universal      Merchant Power Price
  epc               4.0x              7.0%       5.0%           Fixed-Price Backlog

Design: missing data = bucket EXCLUDED from average, not scored zero.
        Pre-revenue SMRs are evaluated solely on cash runway survival timeline.
"""

import json
import os

from config.universe import (
    UNIVERSE, PRE_REVENUE_TICKERS, BACKLOG_RELEVANT_TICKERS,
    get_domain_for_ticker
)
from data.fetch_fundamentals import fetch_balance_sheet_runway, fetch_margin_expansion

OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "manual_overrides.json")

# -- Domain-Aware Threshold Tables ---------------------------------------------
DOMAIN_THRESHOLDS = {
    "fuel_cycle": {
        "net_debt_ebitda_cap": None,
        "roic_tiers":         None,
        "gross_margin_floor": None,
    },
    "components_grid": {
        "net_debt_ebitda_cap": 4.0,
        "roic_tiers": {"high": 0.12, "mid": 0.08, "low": 0.04},
        "gross_margin_floor": 0.18,
    },
    "smr_pureplay": {
        "net_debt_ebitda_cap": None,
        "roic_tiers":         None,
        "gross_margin_floor": None,
    },
    "utilities": {
        "net_debt_ebitda_cap": 5.0,    # Contracted/regulated utility norm
                                        # Asset-backed balance sheets with long-term
                                        # PPAs (e.g. CEG/Microsoft 20-yr) support
                                        # higher leverage than industrial peers
        "roic_tiers":         None,    # Universal
        "gross_margin_floor": None,    # Universal
    },
    "epc": {
        "net_debt_ebitda_cap": 4.0,
        "roic_tiers": {"high": 0.10, "mid": 0.07, "low": 0.03},
        "gross_margin_floor": 0.05,
    },
}

UNIVERSAL_ROIC_TIERS = {"high": 0.15, "mid": 0.10, "low": 0.05}


def _load_manual_overrides() -> dict:
    with open(OVERRIDES_PATH, "r") as f:
        return json.load(f)


def _get_domain_thresholds(domain: str) -> dict:
    return DOMAIN_THRESHOLDS.get(domain, {
        "net_debt_ebitda_cap": None,
        "roic_tiers": None,
        "gross_margin_floor": None,
    })


def score_balance_sheet_runway(ticker: str, domain: str) -> dict:
    is_pre_revenue = ticker in PRE_REVENUE_TICKERS
    result = fetch_balance_sheet_runway(ticker, is_pre_revenue=is_pre_revenue)
    value  = result["value"]
    score  = None
    thresholds = _get_domain_thresholds(domain)

    if is_pre_revenue:
        if value is not None:
            if value >= 12:   score = 10
            elif value >= 8:  score = 7
            elif value >= 4:  score = 4
            else:             score = 1
        else:
            score = 0
        return {"bucket": "balance_sheet_runway", "score": score, "detail": result}

    if value is not None and result["metric_type"] == "net_debt_to_ebitda":
        cap = thresholds.get("net_debt_ebitda_cap")
        if cap is not None:
            if value <= 0:              score = 10
            elif value <= cap * 0.25:   score = 8
            elif value <= cap * 0.50:   score = 6
            elif value <= cap * 0.75:   score = 4
            elif value <= cap:          score = 2
            else:                       score = 0
        else:
            if value <= 0:    score = 10
            elif value <= 1:  score = 8
            elif value <= 2:  score = 6
            elif value <= 3:  score = 4
            elif value <= 4:  score = 2
            else:             score = 0

    return {"bucket": "balance_sheet_runway", "score": score, "detail": result}


def score_margin_expansion(ticker: str, domain: str) -> dict:
    if domain == "smr_pureplay":
        return {"bucket": "margin_expansion", "score": None,
                "detail": "not applicable -- pre-revenue domain"}

    result     = fetch_margin_expansion(ticker)
    sub_scores = []
    thresholds = _get_domain_thresholds(domain)
    roic_tiers = thresholds.get("roic_tiers") or UNIVERSAL_ROIC_TIERS
    gm_floor   = thresholds.get("gross_margin_floor")

    trend = result.get("gross_margin_trend")
    if trend is not None:
        gm_current = result.get("gross_margin_current") or 0
        if gm_floor is not None:
            if gm_current >= gm_floor and trend > 0.02:      sub_scores.append(5)
            elif gm_current >= gm_floor and trend >= 0:       sub_scores.append(3)
            elif gm_current >= gm_floor and trend >= -0.02:   sub_scores.append(1)
            else:                                              sub_scores.append(0)
        else:
            if trend > 0.02:      sub_scores.append(5)
            elif trend >= 0:      sub_scores.append(3)
            elif trend >= -0.02:  sub_scores.append(1)
            else:                 sub_scores.append(0)

    roic = result.get("roic")
    if roic is not None:
        if roic > roic_tiers["high"]:   sub_scores.append(5)
        elif roic > roic_tiers["mid"]:  sub_scores.append(3)
        elif roic > roic_tiers["low"]:  sub_scores.append(1)
        else:                           sub_scores.append(0)

    score = sum(sub_scores) if sub_scores else None
    return {"bucket": "margin_expansion", "score": score, "detail": result}


def score_backlog_momentum(ticker: str, overrides: dict) -> dict:
    if ticker not in BACKLOG_RELEVANT_TICKERS:
        return {"bucket": "backlog_momentum", "score": None,
                "detail": "not applicable to this domain"}

    entry = overrides.get(ticker, {})
    if entry.get("backlog_score_0_10") is not None:
        return {"bucket": "backlog_momentum", "score": entry["backlog_score_0_10"],
                "detail": entry}

    sub_scores = []
    btb = entry.get("book_to_bill")
    if btb is not None:
        sub_scores.append(5 if btb > 1.2 else 3 if btb >= 1.0 else 0)

    growth = entry.get("backlog_growth_yoy")
    if growth is not None:
        sub_scores.append(5 if growth > 0.20 else 3 if growth >= 0 else 0)

    score = sum(sub_scores) if sub_scores else None
    return {"bucket": "backlog_momentum", "score": score, "detail": entry}


def calculate_nqs(ticker: str, overrides: dict = None) -> dict:
    if overrides is None:
        overrides = _load_manual_overrides()

    domain = get_domain_for_ticker(ticker)
    buckets = [
        score_backlog_momentum(ticker, overrides),
        score_balance_sheet_runway(ticker, domain),
        score_margin_expansion(ticker, domain),
    ]

    applicable = [b for b in buckets if b["score"] is not None]
    nqs = round(sum(b["score"] for b in applicable) / len(applicable) * 10, 1) \
          if applicable else None

    return {
        "ticker":          ticker,
        "domain":          domain,
        "nqs":             nqs,
        "buckets_applied": [b["bucket"] for b in applicable],
        "bucket_detail":   buckets,
    }


def run_full_universe() -> list:
    overrides = _load_manual_overrides()
    results   = []
    for domain in UNIVERSE.values():
        for ticker in domain["tickers"]:
            results.append(calculate_nqs(ticker, overrides))
    return sorted(results, key=lambda r: (r["nqs"] is None, -(r["nqs"] or 0)))
"""
Nuclear Quality Score (NQS) scoring engine.

Three buckets, each scored 0-10, averaged across whichever buckets actually
apply to a given ticker's domain, then scaled to a 0-100 NQS for comparability
across domains with different numbers of applicable buckets.

  1. Backlog Momentum     — components_grid and epc domains only (manual data)
  2. Balance Sheet Runway  — all domains (Net Debt/EBITDA or cash-runway path)
  3. Margin Expansion      — all domains, but commonly returns None for
                              pre-revenue SMRs (that's a correct, not missing,
                              result — see notes below)

Design choice: missing data means the bucket is EXCLUDED from the average,
not scored as zero. A pre-revenue SMR with no gross margin isn't "failing"
margin expansion — the metric doesn't exist yet. Scoring it zero would
mechanically tank every SMR pure-play regardless of actual quality, which
defeats the point of having a documented exception layer for them at all.

These thresholds are starter calibration, not backtested. Expect to revisit
them the same way min_score went from 6 to 7 in the options scanner after
evidence came in — these numbers should move once you have a few quarters
of NQS history to backtest against forward returns.
"""

import json
import os

from config.universe import UNIVERSE, PRE_REVENUE_TICKERS, BACKLOG_RELEVANT_TICKERS, get_domain_for_ticker
from data.fetch_fundamentals import fetch_balance_sheet_runway, fetch_margin_expansion

OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "manual_overrides.json")


def _load_manual_overrides() -> dict:
    with open(OVERRIDES_PATH, "r") as f:
        return json.load(f)


def score_balance_sheet_runway(ticker: str) -> dict:
    is_pre_revenue = ticker in PRE_REVENUE_TICKERS
    result = fetch_balance_sheet_runway(ticker, is_pre_revenue=is_pre_revenue)
    value = result["value"]
    score = None

    if value is not None:
        if result["metric_type"] == "net_debt_to_ebitda":
            if value <= 0:
                score = 10
            elif value <= 1:
                score = 8
            elif value <= 2:
                score = 6
            elif value <= 3:
                score = 4
            elif value <= 4:
                score = 2
            else:
                score = 0
        else:  # cash_runway_quarters
            if value >= 12:
                score = 10
            elif value >= 8:
                score = 7
            elif value >= 4:
                score = 4
            else:
                score = 1
    elif is_pre_revenue:
        # No runway figure at all for a pre-revenue name is itself a red
        # flag worth scoring low rather than excluding, unlike margin data.
        score = 0

    return {"bucket": "balance_sheet_runway", "score": score, "detail": result}


def score_margin_expansion(ticker: str) -> dict:
    result = fetch_margin_expansion(ticker)
    sub_scores = []

    trend = result.get("gross_margin_trend")
    if trend is not None:
        if trend > 0.02:
            sub_scores.append(5)
        elif trend >= 0:
            sub_scores.append(3)
        elif trend >= -0.02:
            sub_scores.append(1)
        else:
            sub_scores.append(0)

    roic = result.get("roic")
    if roic is not None:
        if roic > 0.15:
            sub_scores.append(5)
        elif roic > 0.10:
            sub_scores.append(3)
        elif roic > 0.05:
            sub_scores.append(1)
        else:
            sub_scores.append(0)

    score = sum(sub_scores) if sub_scores else None
    return {"bucket": "margin_expansion", "score": score, "detail": result}


def score_backlog_momentum(ticker: str, overrides: dict) -> dict:
    if ticker not in BACKLOG_RELEVANT_TICKERS:
        return {"bucket": "backlog_momentum", "score": None, "detail": "not applicable to this domain"}

    entry = overrides.get(ticker, {})
    if entry.get("backlog_score_0_10") is not None:
        return {"bucket": "backlog_momentum", "score": entry["backlog_score_0_10"], "detail": entry}

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
        score_balance_sheet_runway(ticker),
        score_margin_expansion(ticker),
    ]

    applicable = [b for b in buckets if b["score"] is not None]
    nqs = round(sum(b["score"] for b in applicable) / len(applicable) * 10, 1) if applicable else None

    return {
        "ticker": ticker,
        "domain": domain,
        "nqs": nqs,
        "buckets_applied": [b["bucket"] for b in applicable],
        "bucket_detail": buckets,
    }


def run_full_universe() -> list:
    overrides = _load_manual_overrides()
    results = []
    for domain in UNIVERSE.values():
        for ticker in domain["tickers"]:
            results.append(calculate_nqs(ticker, overrides))
    return sorted(results, key=lambda r: (r["nqs"] is None, -(r["nqs"] or 0)))

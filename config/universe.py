"""
Nuclear Infrastructure Screener — Ticker Universe
Second book under Second Layer Capital.
Mirrors domain structure in nuclear-infrastructure-thesis.md — keep both in sync.

NOTE on backlog_relevant: the Backlog Momentum NQS bucket only makes sense for
domains where companies actually report backlog / book-to-bill (project-driven
revenue). Miners, pre-revenue SMRs, and regulated utilities don't report this
in a comparable way, so they're excluded from that bucket rather than scored
on a metric that doesn't exist for them.
"""

UNIVERSE = {
    "fuel_cycle": {
        "domain_name": "Uranium Fuel Cycle (Mining & Enrichment)",
        "tickers": ["CCJ", "UEC", "DNN", "LEU"],
        "backlog_relevant": False,
        "pre_revenue": [],
    },
    "components_grid": {
        "domain_name": "Reactor Components & Grid Infrastructure",
        "tickers": ["BWXT", "GEV", "FLS", "IR"],
        "backlog_relevant": True,
        "pre_revenue": [],
    },
    "smr_pureplay": {
        "domain_name": "SMR / Advanced Reactor Pure-Plays",
        "tickers": ["OKLO", "SMR"],
        "is_exception_layer": True,
        "backlog_relevant": False,
        "pre_revenue": ["OKLO", "SMR"],
    },
    "utilities": {
        "domain_name": "Utilities Capturing AI Power Premium",
        "tickers": ["CEG", "VST", "TLN"],
        "backlog_relevant": False,
        "pre_revenue": [],
    },
    "epc": {
        "domain_name": "Engineering, Procurement & Construction",
        "tickers": ["J", "FLR"],
        "backlog_relevant": True,
        "pre_revenue": [],
    },
}

WATCHLIST = ["NXE", "URG", "EU", "ISOU"]

ALL_ACTIVE_TICKERS = [t for domain in UNIVERSE.values() for t in domain["tickers"]]
PRE_REVENUE_TICKERS = {t for domain in UNIVERSE.values() for t in domain.get("pre_revenue", [])}
BACKLOG_RELEVANT_TICKERS = {
    t for domain in UNIVERSE.values() if domain["backlog_relevant"] for t in domain["tickers"]
}


def get_domain_for_ticker(ticker):
    """Returns the domain key a ticker belongs to, or None if not in universe."""
    for domain_key, domain in UNIVERSE.items():
        if ticker in domain["tickers"]:
            return domain_key
    return None

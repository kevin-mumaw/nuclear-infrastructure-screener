# Nuclear Infrastructure Screener
Second book under Second Layer Capital. Companion repo to `hypersonic-defense-screener`.

## What this is (v1 scaffold)

A Nuclear Quality Score (NQS) engine across the five domains defined in
`nuclear-infrastructure-thesis.md`. Three scoring buckets, 0-10 each, averaged
across whichever buckets actually apply to a ticker and scaled to 0-100:

1. **Backlog Momentum** — components_grid and epc domains only (BWXT, GEV,
   FLS, IR, J, FLR). Manually maintained in `config/manual_overrides.json`
   since no free API reports backlog or book-to-bill.
2. **Balance Sheet Runway** — all tickers. Net Debt/EBITDA for established
   names, cash-runway-in-quarters for pre-revenue SMRs (OKLO, SMR).
3. **Margin Expansion** — all tickers, via gross margin YoY trend and ROIC.
   Commonly returns N/A for pre-revenue names — that's correct, not broken.

## Setup

```
python -m venv venv
venv\Scripts\activate          (Windows)
pip install -r requirements.txt
```

## Running it

```
python main.py
```

Prints a ranked table of every ticker in the active universe with its NQS
and which buckets contributed to it.

## Before this is trustworthy

- `config/manual_overrides.json` is all `null` right now. Pull backlog growth
  and book-to-bill for BWXT/GEV/FLS/IR/J/FLR from their latest 10-Q or
  investor deck and fill it in — otherwise those six tickers are only being
  scored on 2 of 3 buckets.
- The scoring thresholds in `scoring/nqs_scorer.py` are starter calibration,
  not backtested. Same situation the options scanner was in before min_score
  moved from 6 to 7 — expect to revisit these once there's a few quarters of
  NQS history to check against forward returns.
- No backtesting or Streamlit dashboard yet. This is Phase 1 (the scoring
  engine itself) — Phase 2 (backtesting, thesis overrides) and Phase 2b
  (intelligence monitoring + dashboard) come after this is validated, same
  sequence as the hypersonic build.

## Files

```
nuclear-infrastructure-screener/
├── main.py                       entry point, prints the daily report
├── requirements.txt
├── config/
│   ├── universe.py                ticker universe by domain
│   └── manual_overrides.json      backlog/book-to-bill, manual entry
├── data/
│   └── fetch_fundamentals.py      yfinance pulls for the two automated buckets
└── scoring/
    └── nqs_scorer.py               NQS calculation logic
```

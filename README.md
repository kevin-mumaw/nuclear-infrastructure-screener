# Second Layer Capital — Nuclear Infrastructure Screener ⚛️

A systematic, quantitative "picks-and-shovels" investment framework and stock evaluation engine targeting critical supply chain bottlenecks across the nuclear energy sector. Terminal-only: no dashboard, no web UI. Run everything from the repo root.

The strategy thesis lives in `THESIS.md`.

## 🗺️ Strategy Architecture

15 tickers across 5 domains (`config/universe.py`), plus a 4-name watchlist (NXE, URG, EU, ISOU):

1. **Fuel Cycle** — Uranium mining and enrichment (CCJ, UEC, DNN, LEU).
2. **Reactor Components & Grid Infrastructure** — Industrial hardware manufacturers, naval propulsion suppliers, and grid enablers (BWXT, GEV, FLS, IR).
3. **SMR / Advanced Reactor Pure-Plays** — Pre-revenue names under technical review by the U.S. NRC (OKLO, SMR).
4. **Utilities Capturing AI Power Premium** — Power producers selling into AI data-center demand (CEG, VST, TLN).
5. **Engineering, Procurement & Construction (EPC)** — Complex multi-year scale deployment project handlers (J, FLR).

## 🧮 Nuclear Quality Score (NQS) Engine

`scoring/nqs_scorer.py` calculates a score from 0–100 by averaging the buckets that apply to a ticker's domain, then scaling ×10. Bucket coverage is shown everywhere a score is printed (BKTS column), so a one-bucket 100 is never mistaken for a three-bucket 100:

* **Backlog Momentum** — Book-to-bill and backlog growth, from hand-entered 10-Q data in `config/manual_overrides.json` (Q2 2026). Applies to components_grid and epc only; miners, pre-revenue SMRs, and utilities don't report backlog in a comparable way, so the bucket is excluded for them rather than scored on a metric that doesn't exist.
* **Balance Sheet Runway** — Net Debt/EBITDA against a domain cap for established names; cash runway in quarters for pre-revenue SMRs. A negative EBITDA scores the bucket 0 — a money-loser with debt is known-bad data, not missing data.
* **Margin Expansion** — Gross-margin trend vs a domain floor and ROIC vs domain tiers. Excluded for smr_pureplay.

Bucket counts by domain: components_grid and epc 3 buckets; fuel_cycle and utilities 2; smr_pureplay 1 (runway only). Missing data excludes a bucket from the average — it is never scored zero, except a negative EBITDA (see above).

## ⚙️ Technical Filter Overlay

Before suggesting any capital deployment, allocations run through an execution momentum filter (`data/fetch_fundamentals.py`, RSI-14 with Wilder's smoothing):

* **Trend Gate**: Price must be above its 50-day Simple Moving Average (SMA) for a buy.
* **Momentum Gate**: RSI ≥ 70 flags overbought; RSI ≤ 35 with price above the SMA marks the dip-buying zone.

## 🚀 How to Run

All commands run from the repo root.

* `python main.py` — Score the full 15-ticker universe and print the NQS table.
* `python -m scoring.nqs_scorer` — Same table, standalone.
* `python allocator.py` — Order sheet: target weights, share counts, and technical buy signals. NQS gate ≥ 50, $10,000 budget.
* `python live_signal.py` — Live trading signal with the same NQS engine. NQS gate ≥ 40, $800 budget, USFR as the defensive holding.
* `python backtester.py` — 14/60/200-day momentum backtest. Compares against a true buy-and-hold benchmark (equal dollars, fixed shares, weights drift). The ungated variants are the honest numbers; the NQS-gated variants are labeled in-sample, because today's scores judge historical trades.
* `python earnings_alert.py` — Earnings-date alerts: 14-day action window, 30-day upcoming, 90-day stale check.
* `python gap_warner.py` — Overnight gap warnings: today's open vs prior close, 3.0% threshold.
* `python metrics.py` — Portfolio metrics on the paper-trade ledger.
* `python logger.py` — Paper-trade ledger test (writes to a temp file, never the real ledger).

## 🚀 Repository Blueprint

* `main.py` — Entry point: scores the universe and prints the NQS table.
* `scoring/nqs_scorer.py` — The NQS engine: three buckets, domain thresholds, bucket coverage.
* `config/universe.py` — The 15-ticker universe, 5 domains, watchlist.
* `config/manual_overrides.json` — Hand-entered backlog / book-to-bill data from 10-Qs.
* `data/fetch_fundamentals.py` — Price, fundamental, and technical-signal fetching (yfinance), plus RSI-14 and 50-day SMA.
* `allocator.py` — Order sheet with target weights, share counts, and technical buy signals.
* `live_signal.py` — Live signal and order sheet for real-time trading decisions.
* `backtester.py` — Momentum backtester with true buy-and-hold benchmark and honest ungated variants.
* `earnings_alert.py` — Earnings-date alerts.
* `gap_warner.py` — Overnight gap warnings.
* `metrics.py` — Portfolio metrics on the paper-trade ledger.
* `logger.py` — Paper-trade transaction ledger (`data/trade_log.csv`, currently empty — no real paper trades have been recorded).
* `publish_x.py` — High-impact, character-safe micro-reporting module built under strict 280-character posting guidelines.

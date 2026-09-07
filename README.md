# Second Layer Capital — Nuclear Infrastructure Screener ⚛️

A systematic, quantitative "picks-and-shovels" investment framework and stock evaluation engine targeting critical supply chain bottlenecks across the nuclear energy sector. 

## 🗺️ Strategy Architecture
This system actively monitors structural layers to prioritize companies capturing high-moat infrastructure premiums over standard regulated utilities:
1. **Fuel Cycle Moat** — High-assay low-enriched uranium (HALEU) enrichment monopolies and mining operations.
2. **Reactor Components & Grid Infrastructure** — Industrial hardware manufacturers, naval propulsion suppliers, and grid enablers.
3. **SMR / Advanced Reactor Pure-Plays** — Speculative structural engineers under technical review by the U.S. NRC.
4. **Engineering, Procurement & Construction (EPC)** — Complex multi-year scale deployment project handlers.

## 🧮 Nuclear Quality Score (NQS) Engine
The engine calculates a score from 0-100 by aggregating three core fundamental pillars:
* **Backlog Momentum** — Tracks book-to-bill metrics and 12-month backlog growth pulled directly from SEC filings (`config/manual_overrides.json`).
* **Balance Sheet Runway** — Automatically tracks Net Debt/EBITDA safety or cash runway quarters for pre-revenue names.
* **Margin Expansion** — Evaluates live gross margin trajectories and Return on Invested Capital (ROIC) efficiency.

*Note: Pre-revenue SMR plays automatically utilize specialized evaluation filters to bypass standard margin inputs, protecting them from data distortion.*

## ⚙️ Technical Filter Overlay
Before suggesting any capital deployment, allocations are ran through an execution momentum filter:
* **Trend Gate**: Requires asset price to trace firmly above its 50-day Simple Moving Average (SMA).
* **Momentum Gate**: Checks 14-day RSI parameters to prevent chasing overbought expansions (RSI > 70) and isolate optimal dip-buying zones.

## 🚀 Repository Blueprint
* `allocator.py` — The core terminal execution dashboard calculating target weights, share counts, and technical buy signals.
* `logger.py` — Paper-trade transaction ledger module writing directly to local spreadsheet databases (`data/trade_log.csv`).
* `publish_x.py` — High-impact, character-safe micro-reporting module built under strict 280-character posting guidelines.

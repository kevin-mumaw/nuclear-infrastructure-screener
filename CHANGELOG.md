# Changelog — Second Layer Capital Nuclear Screener

All notable changes, algorithmic updates, and fundamental override calibrations for the systematic Nuclear Infrastructure "Picks & Shovels" strategy will be documented in this file.

## - 2026-06-24 (Advanced Analytics & Risk Tracking Integration)
### Added
- Created `metrics.py` performance analysis engine to dynamically cross-reference `trade_log.csv` against live yfinance tracking data.
- Created `gap_warner.py` overnight volatility monitoring module implementing a automated \(\pm 3.0\%\) price dislocation structural warning alert flag.

## - 2026-06-23 (Automated Paper Ledger Update)
### Added
- Created `logger.py` module to handle local CSV database initialization and automated fractional share scaling metrics.
- Linked transaction logger directly into `allocator.py` to create an interactive terminal trading prompt.

## - 2026-06-22 (Technical Integration Update)
### Added
- Implemented `fetch_technical_signals` function inside `data/fetch_fundamentals.py` to calculate a 14-day RSI and 50-day SMA trend status.
- Upgraded `allocator.py` with an execution logic gate framework to output actionable statuses (`EXECUTE BUY`, `HOLD (Overbought)`, `WAIT (No Trend)`).

## - 2026-06-22
### Added
- Created `allocator.py` module to convert raw NQS metrics into weighted capital distributions and direct share targets.
- Created `publish_x.py` reporting module with built-in character verification hard-capped under the 280-character standard X limit.

### Changed
- Populated `config/manual_overrides.json` with real Q1 2026 corporate data tracking across the `components_grid` and `epc` bottleneck domains (GEV book-to-bill at 1.96, BWXT backlog expansion at +14%).

## - 2026-06-21
### Added
- Initialized core project architecture repository synced with main profile.
- Established `config/universe.py` asset matrix mapping out fuel cycle, components, utilities, and pre-revenue SMR pure-play exception layers.
- Operationalized `data/fetch_fundamentals.py` and `scoring/nqs_scorer.py` engines for automated live yfinance data streams.

# Changelog — Second Layer Capital Nuclear Screener

All notable changes, algorithmic updates, and fundamental override calibrations for the systematic Nuclear Infrastructure "Picks & Shovels" strategy will be documented in this file.

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

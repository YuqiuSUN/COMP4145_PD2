# Stock Trading Strategy

A Streamlit dashboard that backtests simple trading strategies on individual stocks using five years of daily data from Yahoo Finance. Each strategy is compared against a buy-and-hold benchmark and paired with a persistent, interactive watchlist.

## Features

- **Two strategies**
  - Double moving-average crossover: buy on a golden cross, sell on a death cross.
  - Momentum breakout: buy on a new 20-day high, sell on a new 10-day low.
  - All window lengths are configurable from the sidebar.
- **Price chart:** closing prices, strategy-specific moving-average lines, and color-coded buy/sell markers.
- **Equity curve:** strategy equity versus buy-and-hold, followed by the daily drawdown curve.
- **Trade statistics:** total and annualized returns, maximum drawdown, number of trades, win rate, average trade profit, annualized Sharpe ratio, and profit/loss ratio.
- **Detailed trades:** entry and exit dates and prices, holding days, profit, and sell reason for every simulated trade.
- **My watchlist:** validated symbol entry, real-time quotes with color-coded daily changes, one-click backtesting, and inline removal. The list is persisted in SQLite and protected by a unique constraint.
- **Query history:** every page visit is logged together with the page name and strategy type.
- **Single-stock risk analysis:** select a Watchlist stock to review annualized volatility, maximum drawdown, S&P 500 beta, annualized downside risk, historical 95% one-day VaR, and a historical drawdown chart over five years.
- **Risk rating:** green when volatility is ≤20% and drawdown is ≥-20%; yellow when neither exceeds the medium-risk limits (40% volatility and -40% drawdown) and at least one exceeds its low-risk limit; red when either exceeds a medium-risk limit. The higher of the two individual risk levels is used.

## Project structure

- `app.py` — Streamlit UI, charts, caching, and watchlist interactions.
- `trading_strategy.py` — signal generation, the backtesting engine, and performance metrics.
- `database.py` — SQLite setup and data-access functions for the watchlist and query history.
- `requirements.txt` — Python dependencies.
- `stockapp.db` — local SQLite database created automatically on the first run.

## Backtest assumptions

- Initial capital: 10,000.
- One all-in position at a time; no fractional position sizing.
- Signals are generated at the close, and returns begin accruing on the next trading day.
- Commission: 0.1% per side, charged once on entry and once on exit.
- Prices are daily closing prices downloaded from Yahoo Finance over a five-year window.

## Run

Install the dependencies and launch the dashboard from this directory:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

The dashboard loads MSFT by default and caches downloaded data for one hour.

## Changelog
### v5.0 — Single-Stock Risk Analysis

**Risk Analysis**
- Added support to select one stock from the Watchlist for standalone risk evaluation.
- Added calculation of single-stock risk metrics: annualized volatility, maximum drawdown, beta versus S&P 500, 95% 1-day Value at Risk, and annualized downside risk.
- Added a traffic-light risk rating system (green/yellow/red) based on volatility and maximum drawdown.
- Added a historical drawdown chart that marks the maximum drawdown period of the selected stock.

### v4.0 — Portfolio analysis

**Portfolio analysis**

- Added a Portfolio Analysis page that lets users select 2–20 US stocks from their Watchlist and choose a 1-month, 3-month, or 1-year analysis period.
- Added portfolio return calculations using adjusted closing prices. The portfolio starts with equal investments in each stock and is held without rebalancing.
- Added a total return summary, a cumulative return chart, an ending allocation pie chart, and a table showing each stock’s return and ending weight.
- Added clear messages for invalid selections, missing stock data, and insufficient common trading dates.

**Chart compatibility**

- Fixed five Altair chart calls across `app.py` and `portfolio.py` to use `use_container_width=True` with Streamlit 1.50.0.

### v3.0 — Robustness and polish

**Strategy module**

- Added annualized return (CAGR) for both the strategy and the buy-and-hold benchmark.
- Added an in-page warning when the current parameters produce no trades.
- Changed the profit/loss ratio to display N/A when only winning or only losing trades exist.
- Removed the legacy prototype functions that were no longer connected to the app.

**Watchlist and database**

- Added a UNIQUE constraint and a unique index on watchlist symbols; duplicate inserts are now rejected and return a failure flag.
- Added ticker validation before saving a symbol, so invalid symbols cannot be added to the watchlist.
- Added friendly error messages instead of displaying raw exception tracebacks.
- Reworked quote loading from one request per symbol into a single batched download.
- Redesigned the sidebar list from a four-column layout to a cleaner three-column layout.
- Added a success notification when a symbol is removed.
- Reworked database connections with context managers and switched the database to an absolute file path.
- Extended query-history logging to every page, including the page name and strategy type, with protection against duplicate records.

### v2.0 — Strategy expansion and watchlist redesign

**Strategy module**

- Added the momentum breakout strategy alongside the moving-average strategy.
- Added a sidebar strategy selector for switching between the two strategies.
- Added the annualized Sharpe ratio and the profit/loss ratio to the performance summary.
- Added holding days and sell reason to each recorded trade.
- Added a 0.1% commission charged on every buy and sell.
- Added daily drawdown calculation and a dedicated drawdown chart.

**Watchlist and database**

- Replaced the original table view with a card-style list.
- Added inline delete buttons and a symbol count in the section header.
- Added one-click backtesting when a watchlist symbol is selected.
- Added a friendly empty-state guide.
- Added real-time quotes showing the latest price and daily change with color coding.

### v1.0 — Initial release

- Double moving-average crossover strategy backtested against a buy-and-hold benchmark.
- Basic performance metrics: total return, maximum drawdown, number of trades, win rate, and average trade profit.
- Price chart and equity curve.
- Watchlist add/remove with a table display, plus query history, all persisted in SQLite.

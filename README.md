# MSFT Golden-Cross Strategy

A Streamlit dashboard for viewing the existing five-year MSFT golden-cross backtest:

- **Price chart:** closing price, 50-day and 200-day moving averages, plus buy and sell markers.
- **Trade statistics:** totals, win rate, average returns, holding period, and exit reasons.
- **Detailed trades:** the individual simulated trades.
- **My watchlist:** add and remove stock symbols from the sidebar; the list is stored in `stockapp.db`.
- **Query history:** review the 30 most recent visits to the price chart; each visit is recorded after the chart renders successfully.

## Run

Install the dependencies and launch the dashboard from this directory:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

The dashboard downloads MSFT historical prices from Yahoo Finance and caches the result for one hour.

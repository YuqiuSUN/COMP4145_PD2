import altair as alt
import pandas as pd
import streamlit as st
import yfinance as yf

from trading_strategy import (
    calculate_moving_averages,
    get_stock_data,
    generate_momentum_signals,
    generate_signals,
    backtest,
    backtest_momentum,
    performance_summary,
)

from database import (
    add_to_watchlist,
    add_query_history,
    get_query_history,
    get_watchlist,
    init_db,
    remove_from_watchlist,
)
from portfolio import show_portfolio_page
from risk_analysis import show_risk_analysis_page

DOUBLE_MA_STRATEGY = "Double Moving Average Crossover"
MOMENTUM_STRATEGY = "Momentum Breakout"
WATCHLIST_QUOTE_CACHE_TTL = 300

init_db()  


st.set_page_config(page_title="Stock Trading Strategy", page_icon="📈", layout="wide")


@st.cache_data(ttl=3600, show_spinner=False)
def validate_ticker(symbol):
    try:
        return not get_stock_data(symbol, period="1mo").empty
    except Exception:
        return False


@st.cache_data(ttl=3600)
def load_results(ticker, strategy_type, short_window, long_window):
    data = get_stock_data(ticker, period="5y")
    if data.empty:
        return None

    if strategy_type == DOUBLE_MA_STRATEGY:
        data = calculate_moving_averages(
            data, short_window=short_window, long_window=long_window
        )
        data = generate_signals(data)
        data, trades = backtest(data)
    else:
        data = generate_momentum_signals(
            data, buy_window=short_window, sell_window=long_window
        )
        data, trades = backtest_momentum(data)
    summary = performance_summary(data, trades)
    return data, trades, summary


@st.cache_data(ttl=WATCHLIST_QUOTE_CACHE_TTL, show_spinner=False)
def get_watchlist_quotes(symbols):
    """Fetch cached quotes for watchlist symbols with a single download."""
    normalized_symbols = list(
        dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if symbol)
    )
    quotes = {symbol: None for symbol in normalized_symbols}
    if not normalized_symbols:
        return quotes

    try:
        history = yf.download(
            normalized_symbols,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
        )
    except Exception:
        return quotes

    for symbol in normalized_symbols:
        try:
            if isinstance(history.columns, pd.MultiIndex):
                symbol_level = next(
                    level
                    for level in range(history.columns.nlevels)
                    if symbol in history.columns.get_level_values(level)
                )
                symbol_data = history.xs(symbol, axis=1, level=symbol_level)
            else:
                symbol_data = history

            closes = symbol_data["Close"]
            if isinstance(closes, pd.DataFrame):
                closes = closes.iloc[:, 0]
            closes = closes.dropna()
            if len(closes) < 2:
                continue

            latest_close = float(closes.iloc[-1])
            previous_close = float(closes.iloc[-2])
            if previous_close == 0:
                continue
            daily_change_pct = (latest_close / previous_close - 1) * 100
            quotes[symbol] = latest_close, daily_change_pct
        except Exception:
            continue

    return quotes


def show_price_chart(
    ticker, data, trades, strategy_type, short_window, long_window
):
    if strategy_type == DOUBLE_MA_STRATEGY:
        st.subheader(f"{ticker} price and moving averages")
        st.caption(
            "Five years of closing prices and moving averages. "
            "Buy and sell markers show simulated trades."
        )
        series = ["Close", "MA_short", "MA_long"]
        series_colors = ["#4f8bf9", "#f4a340", "#9b72cf"]
    else:
        st.subheader(f"{ticker} price and momentum breakouts")
        st.caption(
            "Five years of closing prices. Buy and sell markers show "
            f"{short_window}-day-high and {long_window}-day-low breakout trades."
        )
        series = ["Close"]
        series_colors = ["#4f8bf9"]

    chart_data = data.rename_axis("Date").reset_index()
    price_lines = chart_data.melt(
        id_vars="Date",
        value_vars=series,
        var_name="Series",
        value_name="Price",
    )
    marker_rows = []
    for trade in trades:
        marker_rows.extend(
            [
                {"Date": trade["BuyDate"], "Price": trade["BuyPrice"], "Action": "Buy"},
                {"Date": trade["SellDate"], "Price": trade["SellPrice"], "Action": "Sell"},
            ]
        )
    markers = pd.DataFrame(marker_rows, columns=["Date", "Price", "Action"])

    x_axis = alt.X("Date:T", title=None)
    base = alt.Chart(price_lines).encode(x=x_axis)
    lines = base.mark_line().encode(
        y=alt.Y("Price:Q", title="Price (USD)"),
        color=alt.Color(
            "Series:N",
            title=None,
            scale=alt.Scale(
                domain=series,
                range=series_colors,
            ),
        ),
        tooltip=[
            alt.Tooltip("Date:T", title="Date"),
            alt.Tooltip("Series:N", title="Series"),
            alt.Tooltip("Price:Q", title="Price", format=",.2f"),
        ],
    )

    chart = lines
    if not markers.empty:
        points = (
            alt.Chart(markers)
            .mark_point(size=110, filled=True, stroke="white", strokeWidth=1)
            .encode(
                x=x_axis,
                y=alt.Y("Price:Q", title="Price (USD)"),
                color=alt.Color(
                    "Action:N",
                    title=None,
                    scale=alt.Scale(
                        domain=["Buy", "Sell"],
                        range=["#20a464", "#e05252"],
                    ),
                ),
                tooltip=[
                    alt.Tooltip("Action:N", title="Trade"),
                    alt.Tooltip("Date:T", title="Date"),
                    alt.Tooltip("Price:Q", title="Price", format=",.2f"),
                ],
            )
        )
        chart = alt.layer(lines, points).resolve_scale(color="independent")

    st.altair_chart(
        chart.properties(height=520).interactive(), use_container_width=True
    )


def show_equity_chart(data):
    st.subheader("Strategy vs. buy-and-hold")
    equity_data = data.rename_axis("Date").reset_index().melt(
        id_vars="Date",
        value_vars=["Strategy", "BuyHold"],
        var_name="Series",
        value_name="Equity",
    )
    chart = (
        alt.Chart(equity_data)
        .mark_line()
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Equity:Q", title="Portfolio value (USD)"),
            color=alt.Color(
                "Series:N",
                title=None,
                scale=alt.Scale(
                    domain=["Strategy", "BuyHold"],
                    range=["#4f8bf9", "#9b72cf"],
                ),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Date"),
                alt.Tooltip("Series:N", title="Portfolio"),
                alt.Tooltip("Equity:Q", title="Value (USD)", format=",.2f"),
            ],
        )
        .properties(height=360)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def show_drawdown_chart(data):
    st.subheader("Daily strategy drawdown")
    drawdown_data = data.rename_axis("Date").reset_index()
    chart = (
        alt.Chart(drawdown_data)
        .mark_line(color="#e05252")
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("DrawdownPct:Q", title="Drawdown (%)"),
            tooltip=[
                alt.Tooltip("Date:T", title="Date"),
                alt.Tooltip(
                    "DrawdownPct:Q", title="Drawdown", format=",.2f"
                ),
            ],
        )
        .properties(height=280)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def show_trade_statistics(summary):
    st.subheader("Backtest performance summary")
    first_row = st.columns(4)
    first_row[0].metric(
        "Strategy total return", f"{summary['strategy_total_return_pct']:.2f}%"
    )
    first_row[1].metric(
        "Buy & hold total return", f"{summary['buy_hold_total_return_pct']:.2f}%"
    )
    first_row[2].metric("Maximum drawdown", f"{summary['max_drawdown_pct']:.2f}%")
    first_row[3].metric("Number of trades", f"{summary['number_of_trades']}")

    second_row = st.columns(3)
    second_row[0].metric("Winning trades", f"{summary['winning_trades']}")
    second_row[1].metric("Win rate", f"{summary['win_rate_pct']:.2f}%")
    second_row[2].metric(
        "Average trade profit", f"{summary['average_trade_profit_pct']:.2f}%"
    )

    third_row = st.columns(2)
    third_row[0].metric(
        "Annualized Sharpe ratio", f"{summary['annualized_sharpe_ratio']:.2f}"
    )
    profit_loss_ratio = summary["profit_loss_ratio"]
    third_row[1].metric(
        "Profit/loss ratio",
        f"{profit_loss_ratio:.2f}" if profit_loss_ratio is not None else "N/A",
    )

    fourth_row = st.columns(2)
    fourth_row[0].metric(
        "Strategy annualized return",
        f"{summary['strategy_annualized_return_pct']:.2f}%",
    )
    fourth_row[1].metric(
        "Buy & hold annualized return",
        f"{summary['buy_hold_annualized_return_pct']:.2f}%",
    )


def show_detailed_trades(trades):
    st.subheader("Detailed trades")
    if not trades:
        st.info("No trades are available to display.")
        return

    display = pd.DataFrame(trades).rename(
        columns={
            "BuyDate": "Buy date",
            "BuyPrice": "Buy price (USD)",
            "SellDate": "Sell date",
            "SellPrice": "Sell price (USD)",
            "HoldingDays": "Holding days",
            "ProfitPct": "Profit (%)",
            "SellReason": "Sell reason",
        }
    )
    st.dataframe(display, hide_index=True, width="stretch")


def show_query_history():
    st.subheader("Recent query history")
    history = get_query_history(30)
    if history.empty:
        st.info("No query history is available yet.")
        return

    display = history.rename(
        columns={
            "id": "ID",
            "symbol": "Symbol",
            "queried_at": "Queried at",
            "note": "Note",
        }
    )
    st.dataframe(display, hide_index=True, width="stretch")


def select_watchlist_symbol(symbol):
    st.session_state["backtest_ticker"] = symbol


strategy_type = st.sidebar.selectbox(
    "Strategy type",
    [DOUBLE_MA_STRATEGY, MOMENTUM_STRATEGY],
    key="strategy_type",
)
selected_ticker = st.sidebar.text_input(
    "Ticker",
    value="MSFT",
    placeholder="e.g. AAPL",
    key="backtest_ticker",
).strip().upper()
if strategy_type == DOUBLE_MA_STRATEGY:
    short_window = st.sidebar.number_input(
        "Short moving-average window",
        min_value=1,
        value=5,
        step=1,
        key="short_window",
    )
    long_window = st.sidebar.number_input(
        "Long moving-average window",
        min_value=1,
        value=20,
        step=1,
        key="long_window",
    )
else:
    short_window = st.sidebar.number_input(
        "Buy breakout window",
        min_value=1,
        value=20,
        step=1,
        key="momentum_buy_window",
    )
    long_window = st.sidebar.number_input(
        "Sell breakout window",
        min_value=1,
        value=10,
        step=1,
        key="momentum_sell_window",
    )

st.sidebar.divider()
watchlist = get_watchlist()
st.sidebar.header(f"🌟 My Watchlist ({len(watchlist)})")
if "watchlist_added_symbol" in st.session_state:
    added_symbol = st.session_state.pop("watchlist_added_symbol")
    st.sidebar.success(f"Added {added_symbol}")
if "watchlist_removed_symbol" in st.session_state:
    removed_symbol = st.session_state.pop("watchlist_removed_symbol")
    st.sidebar.success(f"Removed {removed_symbol} from your watchlist.")

new_symbol = st.sidebar.text_input(
    "Add stock symbol",
    placeholder="e.g. AAPL",
    key="watchlist_symbol_input",
)
if st.sidebar.button("Add", key="add_watchlist_symbol"):
    symbol = new_symbol.strip().upper()
    if not symbol:
        st.sidebar.warning("Enter a stock symbol.")
    elif not validate_ticker(symbol):
        st.sidebar.warning("That is not a valid stock symbol.")
    else:
        if add_to_watchlist(symbol):
            st.session_state["watchlist_added_symbol"] = symbol
            st.rerun()
        else:
            st.sidebar.info(f"{symbol} is already in your watchlist.")

if watchlist.empty:
    st.sidebar.info("Your watchlist is empty. Add a stock symbol to get started.")
else:
    watchlist_stocks = list(watchlist.itertuples(index=False))
    watchlist_quotes = get_watchlist_quotes(
        [str(stock.symbol) for stock in watchlist_stocks]
    )
    for stock in watchlist_stocks:
        symbol = str(stock.symbol)
        symbol_column, quote_column, remove_column = st.sidebar.columns(
            [1.2, 1.5, 0.7]
        )
        symbol_column.button(
            symbol,
            key=f"watchlist_select_{stock.id}",
            on_click=select_watchlist_symbol,
            args=(symbol,),
            use_container_width=True,
        )
        quote = watchlist_quotes.get(symbol.upper())
        if quote is None:
            quote_column.caption("Data unavailable")
        else:
            latest_close, daily_change_pct = quote
            quote_color = (
                "green"
                if daily_change_pct > 0
                else "red" if daily_change_pct < 0 else "gray"
            )
            quote_column.markdown(
                f":{quote_color}[${latest_close:,.2f} "
                f"({daily_change_pct:+.2f}%)]"
            )
        if remove_column.button(
            "Delete",
            key=f"watchlist_delete_{stock.id}",
            use_container_width=True,
        ):
            remove_from_watchlist(symbol)
            st.session_state["watchlist_removed_symbol"] = symbol
            st.rerun()

st.sidebar.divider()
page = st.sidebar.radio(
    "Page",
    [
        "Price chart",
        "Equity curve",
        "Trade statistics",
        "Detailed trades",
        "Query history",
        "Portfolio Analysis",
        "Single Stock Risk Analysis",
    ],
)

if page == "Portfolio Analysis":
    show_portfolio_page(watchlist["symbol"].tolist())
    st.stop()
elif page == "Single Stock Risk Analysis":
    risk_symbol = show_risk_analysis_page(watchlist["symbol"].tolist())
    if risk_symbol:
        view_key = f"{risk_symbol}:{page}"
        if st.session_state.get("last_view") != view_key:
            add_query_history(
                risk_symbol,
                note=f"Viewed {page} for {risk_symbol}",
            )
        st.session_state["last_view"] = view_key
    st.stop()

st.sidebar.divider()
if strategy_type == DOUBLE_MA_STRATEGY:
    st.sidebar.markdown(
        "**Strategy**  \n"
        "Buy when the short moving average crosses above the long average; "
        "sell when it crosses below."
    )
else:
    st.sidebar.markdown(
        "**Strategy**  \n"
        "Buy at a new buy-window high and sell at a new sell-window low."
    )

st.title(f"{selected_ticker or 'Stock'} {strategy_type}")
if strategy_type == DOUBLE_MA_STRATEGY:
    st.caption(
        f"Five-year backtest using {short_window}-day and "
        f"{long_window}-day moving averages"
    )
else:
    st.caption(
        f"Five-year backtest using a {short_window}-day high breakout "
        f"and {long_window}-day low breakout"
    )

if not selected_ticker:
    st.warning("Enter a stock ticker to run the backtest.")
elif strategy_type == DOUBLE_MA_STRATEGY and short_window >= long_window:
    st.warning("The short moving-average window must be less than the long window.")
else:
    try:
        results = load_results(
            selected_ticker, strategy_type, short_window, long_window
        )
    except Exception:
        st.error("Unable to load data for this ticker. Please try again later.")
    else:
        if results is None:
            st.error(
                "No data found for the ticker. Please check the symbol and try again."
            )
        else:
            data, trades, summary = results

            if not trades:
                st.warning(
                    "No trades were generated with the current parameters. Try "
                    "adjusting the window lengths or selecting a different stock."
                )

            if page == "Price chart":
                show_price_chart(
                    selected_ticker,
                    data,
                    trades,
                    strategy_type,
                    short_window,
                    long_window,
                )
            elif page == "Equity curve":
                show_equity_chart(data)
                show_drawdown_chart(data)
            elif page == "Trade statistics":
                show_trade_statistics(summary)
            elif page == "Detailed trades":
                show_detailed_trades(trades)
            else:
                show_query_history()

            view_key = f"{selected_ticker}:{page}:{strategy_type}"
            if st.session_state.get("last_view") != view_key:
                add_query_history(
                    selected_ticker,
                    note=f"Viewed {page} for {selected_ticker} using {strategy_type}",
                )
            st.session_state["last_view"] = view_key

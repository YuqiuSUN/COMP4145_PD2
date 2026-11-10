import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
import yfinance as yf


def calculate_portfolio_returns(adjusted_close: pd.DataFrame) -> dict:
    """Calculate equal-initial-investment, buy-and-hold portfolio returns.

    Returns are decimals (for example, 0.025 represents 2.5%). Ending weights
    are also decimals and account for each stock's growth without rebalancing.
    """
    if adjusted_close.empty or len(adjusted_close.columns) == 0:
        raise ValueError("Provide adjusted closing prices for at least one stock.")
    if adjusted_close.columns.has_duplicates:
        raise ValueError("Each stock must have a unique column name.")

    prices = adjusted_close.sort_index().apply(pd.to_numeric, errors="coerce")
    valid_prices = prices.where(np.isfinite(prices) & prices.gt(0))

    stocks_without_prices = [
        str(stock)
        for stock in valid_prices.columns
        if not valid_prices[stock].notna().any()
    ]
    if stocks_without_prices:
        stock_names = ", ".join(stocks_without_prices)
        raise ValueError(f"No valid positive prices found for: {stock_names}.")

    common_prices = valid_prices.dropna(axis=0, how="any")
    if len(common_prices) < 2:
        raise ValueError(
            "At least two dates with valid positive prices for every stock are required."
        )

    starting_prices = common_prices.iloc[0]
    normalized_prices = common_prices.divide(starting_prices)
    cumulative_returns = normalized_prices.mean(axis=1).sub(1)
    cumulative_returns.name = "cumulative_return"

    stock_returns = common_prices.iloc[-1].divide(starting_prices).sub(1)
    stock_returns.name = "stock_return"
    ending_values = common_prices.iloc[-1].divide(starting_prices)
    ending_weights = ending_values.divide(ending_values.sum())
    ending_weights.name = "ending_weight"

    return {
        "cumulative_returns": cumulative_returns,
        "total_return": float(cumulative_returns.iloc[-1]),
        "stock_returns": stock_returns,
        "ending_weights": ending_weights,
        "start_date": common_prices.index[0],
        "end_date": common_prices.index[-1],
    }


@st.cache_data(ttl=3600, show_spinner=False)
def load_adjusted_close(
    symbols: tuple[str, ...], period: str
) -> pd.DataFrame:
    """Fetch adjusted closing prices for USD-denominated US stocks."""
    for symbol in symbols:
        try:
            info = yf.Ticker(symbol).get_info()
        except Exception as error:
            raise RuntimeError(
                f"Unable to verify US/USD listing information for {symbol}."
            ) from error
        if info.get("region") != "US" or info.get("currency") != "USD":
            raise ValueError(
                f"{symbol} is not verified as a US stock priced in USD."
            )

    history = yf.download(
        list(symbols),
        period=period,
        auto_adjust=True,
        group_by="ticker",
        progress=False,
    )
    prices = pd.DataFrame(index=history.index)
    if isinstance(history.columns, pd.MultiIndex):
        symbol_level = next(
            (
                level
                for level in range(history.columns.nlevels)
                if all(
                    symbol in history.columns.get_level_values(level)
                    for symbol in symbols
                )
            ),
            None,
        )
    else:
        symbol_level = None

    for symbol in symbols:
        symbol_data = None
        if isinstance(history.columns, pd.MultiIndex) and symbol_level is not None:
            symbol_data = history.xs(symbol, axis=1, level=symbol_level)
        elif not isinstance(history.columns, pd.MultiIndex):
            symbol_data = history

        close = None
        if symbol_data is not None:
            for column in symbol_data.columns:
                if str(column).casefold() in {"close", "adj close"}:
                    close = symbol_data[column]
                    break
        prices[symbol] = close if close is not None else np.nan

    return prices


def show_portfolio_page(watchlist_symbols: list[str]) -> None:
    """Render the watchlist-based portfolio analysis page."""
    st.title("Portfolio Analysis")
    st.caption(
        "For US stocks priced in USD. The portfolio starts with equal weights "
        "and is held without rebalancing."
    )

    symbols = list(
        dict.fromkeys(
            str(symbol).strip().upper()
            for symbol in watchlist_symbols
            if str(symbol).strip()
        )
    )
    if not symbols:
        st.info("Your Watchlist is empty. Add stocks in the sidebar to get started.")
        return

    selected_symbols = st.multiselect(
        "Select 2 to 20 distinct Watchlist stocks",
        options=symbols,
        max_selections=min(20, len(symbols)),
        key="portfolio_selected_symbols",
    )
    period_label = st.selectbox(
        "Analysis period",
        ["1M", "3M", "1Y"],
        key="portfolio_analysis_period",
    )

    if st.button("Analyze Portfolio", key="analyze_portfolio"):
        if not 2 <= len(selected_symbols) <= 20:
            st.warning("Select between 2 and 20 distinct stocks to continue.")
            return

        periods = {"1M": "1mo", "3M": "3mo", "1Y": "1y"}
        try:
            with st.spinner("Loading adjusted closing prices..."):
                prices = load_adjusted_close(
                    tuple(selected_symbols), periods[period_label]
                )
        except ValueError as error:
            st.error(str(error))
            return
        except Exception:
            st.error(
                "Unable to fetch portfolio price data right now. Please try again."
            )
            return

        try:
            result = calculate_portfolio_returns(prices)
        except ValueError as error:
            st.error(str(error))
            return

        st.metric("Portfolio Total Return", f"{result['total_return']:.2%}")
        st.caption(
            "Actual analysis dates: "
            f"{result['start_date']:%Y-%m-%d} to {result['end_date']:%Y-%m-%d}"
        )

        cumulative = (
            result["cumulative_returns"]
            .rename_axis("Date")
            .rename("Cumulative return")
            .reset_index()
        )
        line_chart = (
            alt.Chart(cumulative)
            .mark_line(color="#4f8bf9")
            .encode(
                x=alt.X("Date:T", title=None),
                y=alt.Y(
                    "Cumulative return:Q",
                    title="Cumulative return",
                    axis=alt.Axis(format=".1%"),
                ),
                tooltip=[
                    alt.Tooltip("Date:T", title="Date"),
                    alt.Tooltip(
                        "Cumulative return:Q",
                        title="Cumulative return",
                        format=".2%",
                    ),
                ],
            )
            .properties(height=360)
            .interactive()
        )
        st.subheader("Cumulative Portfolio Return")
        st.altair_chart(line_chart, use_container_width=True)

        allocation = pd.DataFrame(
            {
                "Stock": result["ending_weights"].index,
                "Ending weight": result["ending_weights"].values,
            }
        )
        pie_chart = (
            alt.Chart(allocation)
            .mark_arc()
            .encode(
                theta=alt.Theta("Ending weight:Q", stack=True),
                color=alt.Color("Stock:N", title=None),
                tooltip=[
                    alt.Tooltip("Stock:N", title="Stock"),
                    alt.Tooltip(
                        "Ending weight:Q", title="Ending weight", format=".2%"
                    ),
                ],
            )
            .properties(height=360)
        )
        st.subheader("Ending Allocation")
        st.altair_chart(pie_chart, use_container_width=True)

        returns_table = pd.concat(
            [result["stock_returns"], result["ending_weights"]], axis=1
        ).rename(
            columns={
                "stock_return": "Return",
                "ending_weight": "Ending portfolio weight",
            }
        )
        returns_table.index.name = "Stock"
        st.subheader("Stock Returns and Weights")
        st.dataframe(
            returns_table.style.format("{:.2%}"),
            hide_index=False,
            width="stretch",
        )

import math

import altair as alt
import pandas as pd
import streamlit as st
import yfinance as yf


TRADING_DAYS_PER_YEAR = 252
LOW_VOLATILITY_THRESHOLD = 0.20
MEDIUM_VOLATILITY_THRESHOLD = 0.40
LOW_DRAWDOWN_THRESHOLD = -0.20
MEDIUM_DRAWDOWN_THRESHOLD = -0.40


def calculate_historical_drawdown(prices: pd.DataFrame) -> pd.Series:
    """Calculate daily drawdown from prior peaks using common closing dates."""
    if not {"Stock", "S&P 500"}.issubset(prices.columns):
        raise ValueError("Stock and S&P 500 closing prices are required.")

    clean_prices = prices[["Stock", "S&P 500"]].apply(
        pd.to_numeric, errors="coerce"
    )
    clean_prices = clean_prices.where(clean_prices.gt(0)).dropna()
    if clean_prices.empty:
        raise ValueError("No common valid closing prices are available.")

    stock_prices = clean_prices["Stock"]
    drawdown = stock_prices / stock_prices.cummax() - 1
    drawdown.name = "Drawdown"
    return drawdown


@st.cache_data(ttl=3600, show_spinner=False)
def load_risk_price_history(symbol: str) -> pd.DataFrame:
    """Load five years of daily closing prices for a stock and the S&P 500."""
    prices = {}
    for ticker, label in ((symbol, "Stock"), ("^GSPC", "S&P 500")):
        history = yf.Ticker(ticker).history(period="5y", auto_adjust=False)
        if history.empty or "Close" not in history:
            raise ValueError(f"No historical closing prices found for {ticker}.")

        close = pd.to_numeric(history["Close"], errors="coerce")
        prices[label] = close.where(close.gt(0))

    return pd.DataFrame(prices)


def calculate_risk_metrics(prices: pd.DataFrame) -> dict[str, float]:
    """Calculate annualized risk measures from aligned daily closing prices."""
    drawdown = calculate_historical_drawdown(prices)
    clean_prices = prices[["Stock", "S&P 500"]].apply(
        pd.to_numeric, errors="coerce"
    )
    clean_prices = clean_prices.where(clean_prices.gt(0)).dropna()
    returns = clean_prices.pct_change(fill_method=None)
    returns = returns.replace(
        [float("inf"), float("-inf")], float("nan")
    ).dropna()
    if len(returns) < 2:
        raise ValueError(
            "At least three common closing-price dates are required to calculate risk."
        )

    stock_returns = returns["Stock"]
    market_returns = returns["S&P 500"]
    market_variance = market_returns.var(ddof=1)
    if not math.isfinite(market_variance) or market_variance == 0:
        raise ValueError(
            "S&P 500 returns do not have enough variation to calculate beta."
        )

    downside_returns = stock_returns.clip(upper=0)

    return {
        "annualized_volatility": float(
            stock_returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)
        ),
        "maximum_drawdown": float(drawdown.min()),
        "beta": float(stock_returns.cov(market_returns) / market_variance),
        "annualized_downside_risk": float(
            math.sqrt((downside_returns**2).mean() * TRADING_DAYS_PER_YEAR)
        ),
        "var_95": float(-stock_returns.quantile(0.05)),
    }


def classify_risk(metrics: dict[str, float]) -> tuple[str, str, str]:
    """Return the higher of the volatility and maximum-drawdown risk levels."""
    volatility = metrics["annualized_volatility"]
    drawdown = metrics["maximum_drawdown"]

    if (
        volatility > MEDIUM_VOLATILITY_THRESHOLD
        or drawdown < MEDIUM_DRAWDOWN_THRESHOLD
    ):
        return "High", "🔴", "error"
    if volatility > LOW_VOLATILITY_THRESHOLD or drawdown < LOW_DRAWDOWN_THRESHOLD:
        return "Medium", "🟡", "warning"
    return "Low", "🟢", "success"


def show_risk_analysis_page(watchlist_symbols: list[str]) -> str | None:
    """Render the watchlist-based single-stock risk analysis page."""
    st.title("Single Stock Risk Analysis")
    st.caption(
        "Risk measures use five years of daily closing prices. "
        "Beta is calculated against the S&P 500 (^GSPC)."
    )

    symbols = list(
        dict.fromkeys(
            str(symbol).strip().upper()
            for symbol in watchlist_symbols
            if str(symbol).strip()
        )
    )
    if not symbols:
        st.info("Your Watchlist is empty. Add a stock in the sidebar to get started.")
        return None

    selected_index = (
        symbols.index(st.session_state["risk_analysis_ticker"])
        if st.session_state.get("risk_analysis_ticker") in symbols
        else 0
    )
    symbol = st.selectbox(
        "Select a stock from your Watchlist",
        options=symbols,
        index=selected_index,
        key="risk_analysis_ticker",
    )

    try:
        with st.spinner(f"Loading five years of closing prices for {symbol}..."):
            prices = load_risk_price_history(symbol)
        metrics = calculate_risk_metrics(prices)
    except ValueError as error:
        st.warning(str(error))
        return symbol
    except Exception:
        st.error("Unable to load risk data right now. Please try again later.")
        return symbol

    risk_level, indicator, message_type = classify_risk(metrics)
    st.subheader("Risk rating")
    message = (
        f"{indicator} **{risk_level} risk** — based on annualized volatility "
        "and maximum drawdown; the higher of the two ratings is shown."
    )
    getattr(st, message_type)(message)

    columns = st.columns(5)
    columns[0].metric(
        "Annualized volatility", f"{metrics['annualized_volatility']:.2%}"
    )
    columns[1].metric("Maximum drawdown", f"{metrics['maximum_drawdown']:.2%}")
    columns[2].metric("Beta vs. S&P 500", f"{metrics['beta']:.2f}")
    columns[3].metric(
        "Annualized downside risk",
        f"{metrics['annualized_downside_risk']:.2%}",
    )
    columns[4].metric("95% 1-day VaR", f"{metrics['var_95']:.2%}")
    st.caption(
        "Downside risk is the annualized downside deviation relative to a 0% "
        "daily return. VaR is the historical 95th-percentile one-day loss. "
        "Risk thresholds: low at volatility ≤20% and drawdown ≥-20%; medium "
        "at volatility ≤40% and drawdown ≥-40%; otherwise high."
    )

    drawdown_data = (
        calculate_historical_drawdown(prices)
        .rename_axis("Date")
        .reset_index()
    )
    drawdown_chart = (
        alt.Chart(drawdown_data)
        .mark_area(color="#e05252", opacity=0.65)
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y(
                "Drawdown:Q",
                title="Drawdown from prior peak",
                axis=alt.Axis(format=".0%"),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Date"),
                alt.Tooltip("Drawdown:Q", title="Drawdown", format=".2%"),
            ],
        )
        .properties(height=320)
        .interactive()
    )
    st.subheader("Historical drawdown")
    st.altair_chart(drawdown_chart, use_container_width=True)
    return symbol

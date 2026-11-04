import altair as alt
import pandas as pd
import streamlit as st

from trading_strategy import (
    calculate_moving_averages,
    get_stock_data,
    identify_golden_cross,
    implement_strategy,
)


st.set_page_config(page_title="MSFT Trading Strategy", page_icon="📈", layout="wide")


@st.cache_data(ttl=3600)
def load_results():
    data = get_stock_data("MSFT", period="5y")
    if data.empty:
        raise ValueError("Yahoo Finance returned no MSFT price data.")

    data = calculate_moving_averages(data)
    data = identify_golden_cross(data)
    positions = implement_strategy(data)
    return data, positions


def show_price_chart(data, positions):
    st.subheader("MSFT price and moving averages")
    st.caption("Five years of closing prices. Buy and sell markers show simulated trades.")

    chart_data = data.rename_axis("Date").reset_index()
    price_lines = chart_data.melt(
        id_vars="Date",
        value_vars=["Close", "MA50", "MA200"],
        var_name="Series",
        value_name="Price",
    )
    marker_rows = []
    for trade in positions.itertuples(index=False):
        marker_rows.extend(
            [
                {"Date": trade.BuyDate, "Price": trade.BuyPrice, "Action": "Buy"},
                {"Date": trade.SellDate, "Price": trade.SellPrice, "Action": "Sell"},
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
                domain=["Close", "MA50", "MA200"],
                range=["#4f8bf9", "#f4a340", "#9b72cf"],
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

    st.altair_chart(chart.properties(height=520).interactive(), width="stretch")


def show_trade_statistics(positions):
    st.subheader("Overall trade statistics")
    if positions.empty:
        st.info("No golden-cross trades were found for this period.")
        return

    total_trades = len(positions)
    winners = positions.loc[positions["ProfitPct"] > 0]
    losers = positions.loc[positions["ProfitPct"] <= 0]
    win_rate = len(winners) / total_trades * 100
    average_profit = positions["ProfitPct"].mean()
    average_holding = positions["HoldingDays"].mean()
    target_exits = positions["SellReason"].eq("Target reached").sum()

    first_row = st.columns(4)
    first_row[0].metric("Total trades", f"{total_trades}")
    first_row[1].metric("Winning trades", f"{len(winners)}")
    first_row[2].metric("Losing trades", f"{len(losers)}")
    first_row[3].metric("Win rate", f"{win_rate:.2f}%")

    second_row = st.columns(4)
    second_row[0].metric("Average profit / trade", f"{average_profit:.2f}%")
    second_row[1].metric(
        "Average winning trade",
        f"{winners['ProfitPct'].mean():.2f}%" if not winners.empty else "—",
    )
    second_row[2].metric(
        "Average losing trade",
        f"{losers['ProfitPct'].mean():.2f}%" if not losers.empty else "—",
    )
    second_row[3].metric("Average holding period", f"{average_holding:.1f} days")

    st.caption(
        f"Exit reasons: {target_exits} reached the 15% target; "
        f"{total_trades - target_exits} reached the 60-day maximum holding period."
    )


def show_detailed_trades(positions):
    st.subheader("Detailed trades")
    if positions.empty:
        st.info("No trades are available to display.")
        return

    display = positions.rename(
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


st.title("MSFT Golden-Cross Strategy")
st.caption("Five-year moving-average backtest")

page = st.sidebar.radio(
    "Page",
    ["Price chart", "Trade statistics", "Detailed trades"],
)
st.sidebar.divider()
st.sidebar.markdown(
    "**Strategy**  \n"
    "Buy when the 50-day moving average crosses above the 200-day average. "
    "Sell at a 15% gain or after 60 calendar days."
)

data, positions = load_results()

if page == "Price chart":
    show_price_chart(data, positions)
elif page == "Trade statistics":
    show_trade_statistics(positions)
else:
    show_detailed_trades(positions)

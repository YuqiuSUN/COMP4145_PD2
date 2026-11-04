import pandas as pd
import yfinance as yf


def get_stock_data(ticker, period="5y"):
    """Download historical stock data from Yahoo Finance."""
    stock = yf.Ticker(ticker)
    return stock.history(period=period)


def calculate_moving_averages(data):
    """Add 50-day and 200-day simple moving averages."""
    data = data.copy()
    data["MA50"] = data["Close"].rolling(window=50).mean()
    data["MA200"] = data["Close"].rolling(window=200).mean()
    return data


def identify_golden_cross(data):
    """Add a boolean column marking when the 50-day MA crosses above the 200-day MA."""
    data = data.copy()
    data["Signal"] = 0
    data["GoldenCross"] = (data["MA50"] > data["MA200"]) & (
        data["MA50"].shift(1) <= data["MA200"].shift(1)
    )
    return data


def implement_strategy(data):
    """Simulate buying on golden crosses and selling at +15% or after 60 days."""
    positions = []

    # The 200-day moving average needs 200 observations to become available.
    data = data.iloc[200:].copy()
    buy_dates = data.loc[data["GoldenCross"] == True].index.tolist()

    for buy_date in buy_dates:
        buy_price = data.loc[buy_date, "Close"]
        target_price = buy_price * 1.15
        max_sell_date = buy_date + pd.Timedelta(days=60)
        sell_period = data.loc[buy_date:max_sell_date]

        target_reached = sell_period.loc[sell_period["Close"] >= target_price]
        if not target_reached.empty:
            sell_date = target_reached.index[0]
            sell_price = target_reached.loc[sell_date, "Close"]
            sell_reason = "Target reached"
        else:
            sell_date_candidates = sell_period.index.tolist()
            if not sell_date_candidates:
                continue
            sell_date = sell_date_candidates[-1]
            sell_price = data.loc[sell_date, "Close"]
            sell_reason = "Max holding period"

        holding_days = (sell_date - buy_date).days
        profit_pct = (sell_price / buy_price - 1) * 100
        positions.append(
            {
                "BuyDate": buy_date,
                "BuyPrice": buy_price,
                "SellDate": sell_date,
                "SellPrice": sell_price,
                "HoldingDays": holding_days,
                "ProfitPct": profit_pct,
                "SellReason": sell_reason,
            }
        )

    return pd.DataFrame(positions)


def analyze_results(positions):
    """Print a summary of the simulated trades and return their details."""
    if positions.empty:
        return "No trading signals detected"

    total_trades = len(positions)
    win_trades = len(positions.loc[positions["ProfitPct"] > 0])
    loss_trades = total_trades - win_trades
    win_rate = win_trades / total_trades * 100 if total_trades > 0 else 0
    avg_profit = positions["ProfitPct"].mean()

    print("\n===== Trading Strategy Results (Golden Cross) =====")
    print(f"Total Trades: {total_trades}")
    print(f"Winning Trades: {win_trades} ({win_rate:.2f}%)")
    print(f"Losing Trades: {loss_trades}")
    print(f"Average Profit: {avg_profit:.2f}%")

    return positions


def main():
    data = get_stock_data("MSFT")
    data = calculate_moving_averages(data)
    data = identify_golden_cross(data)
    positions = implement_strategy(data)
    analyze_results(positions)
    return positions


if __name__ == "__main__":
    positions = main()
    print("\nDetailed Trades:")
    print(positions.to_string())
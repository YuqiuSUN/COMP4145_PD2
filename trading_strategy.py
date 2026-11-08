import pandas as pd
import yfinance as yf


def get_stock_data(ticker, period="5y"):
    """Download historical stock data from Yahoo Finance."""
    stock = yf.Ticker(ticker)
    return stock.history(period=period)


def calculate_moving_averages(data, short_window=5, long_window=20):
    """Add simple moving averages using the configured window lengths."""
    data = data.copy()
    # Each average uses the requested number of closing-price observations.
    data["MA_short"] = data["Close"].rolling(window=short_window).mean()
    data["MA_long"] = data["Close"].rolling(window=long_window).mean()
    return data


def generate_signals(data):
    """Add holding-state and trade columns for moving-average crossovers."""
    data = data.copy()
    above = data["MA_short"] > data["MA_long"]
    below = data["MA_short"] < data["MA_long"]

    data["Signal"] = above.astype(int)
    # Compare with the prior row to mark only the day each crossover occurs.
    golden_cross = above & (
        data["MA_short"].shift(1) <= data["MA_long"].shift(1)
    )
    death_cross = below & (
        data["MA_short"].shift(1) >= data["MA_long"].shift(1)
    )
    data["Trade"] = ""
    data.loc[golden_cross, "Trade"] = "Buy"
    data.loc[death_cross, "Trade"] = "Sell"
    return data


def generate_momentum_signals(data, buy_window=20, sell_window=10):
    """Buy on a buy-window closing high and sell on a sell-window closing low."""
    data = data.copy()
    previous_high = data["Close"].shift(1).rolling(window=buy_window).max()
    previous_low = data["Close"].shift(1).rolling(window=sell_window).min()
    new_high = data["Close"] > previous_high
    new_low = data["Close"] < previous_low

    holding = False
    signals = []
    trades = []
    for buy_breakout, sell_breakout in zip(new_high, new_low):
        if not holding and buy_breakout:
            holding = True
            trades.append("Buy")
        elif holding and sell_breakout:
            holding = False
            trades.append("Sell")
        else:
            trades.append("")
        signals.append(int(holding))

    data["Signal"] = signals
    data["Trade"] = trades
    return data


def _backtest(data, initial_capital, commission_rate, sell_reason):
    """Run shared backtest calculations, transaction fees, and daily drawdown.

    Assumes one all-in position at a time. Signals are generated at the close,
    and returns begin accruing on the next trading day. The default commission
    rate is 0.001 (0.1%) per side, charged once on entry and once on exit.
    Under the all-in assumption, each fee is deducted as a proportion of that
    day's portfolio value.
    """
    data = data.copy()
    daily_returns = data["Close"].pct_change().fillna(0)

    # Trades at a close affect returns only from the following close onward.
    held_during_day = data["Signal"].shift(1, fill_value=0)
    strategy_returns = daily_returns * held_during_day
    previous_signal = data["Signal"].shift(1, fill_value=0)
    buy_events = (data["Signal"] == 1) & (previous_signal == 0)
    sell_events = (data["Signal"] == 0) & (previous_signal == 1)
    transaction_count = buy_events.astype(int) + sell_events.astype(int)
    net_strategy_returns = (
        (1 + strategy_returns) * (1 - commission_rate) ** transaction_count - 1
    )

    data["BuyHold"] = initial_capital * (1 + daily_returns).cumprod()
    data["Strategy"] = initial_capital * (1 + net_strategy_returns).cumprod()
    data["DrawdownPct"] = (
        data["Strategy"] / data["Strategy"].cummax() - 1
    ) * 100

    trades = []
    buy_date = None
    buy_price = None
    for date, row in data.iterrows():
        if row["Signal"] == 1 and buy_date is None:
            buy_date = date
            buy_price = row["Close"]
        elif row["Signal"] == 0 and buy_date is not None:
            sell_price = row["Close"]
            trades.append(
                {
                    "BuyDate": buy_date,
                    "BuyPrice": buy_price,
                    "SellDate": date,
                    "SellPrice": sell_price,
                    "HoldingDays": (date - buy_date).days,
                    "ProfitPct": (
                        (sell_price / buy_price) * (1 - commission_rate) ** 2 - 1
                    )
                    * 100,
                    "SellReason": sell_reason,
                }
            )
            buy_date = None
            buy_price = None

    return data, trades


def backtest(data, initial_capital=10000, commission_rate=0.001):
    """Backtest moving-average signals.

    Assumes one all-in position at a time. Signals are generated at the close,
    and returns begin accruing on the next trading day. The default commission
    rate is 0.001 (0.1%) per side, charged once on entry and once on exit.
    Under the all-in assumption, each fee is deducted as a proportion of that
    day's portfolio value.
    """
    return _backtest(
        data,
        initial_capital,
        commission_rate,
        "Moving-average death cross sell",
    )


def backtest_momentum(data, initial_capital=10000, commission_rate=0.001):
    """Backtest momentum signals.

    Assumes one all-in position at a time. Signals are generated at the close,
    and returns begin accruing on the next trading day. The default commission
    rate is 0.001 (0.1%) per side, charged once on entry and once on exit.
    Under the all-in assumption, each fee is deducted as a proportion of that
    day's portfolio value.
    """
    return _backtest(
        data,
        initial_capital,
        commission_rate,
        "Momentum low breakout sell",
    )


def performance_summary(data, trades):
    """Return portfolio and trade performance metrics."""
    strategy_equity = data["Strategy"]
    buy_hold_equity = data["BuyHold"]
    trade_count = len(trades)
    winning_trades = sum(trade["ProfitPct"] > 0 for trade in trades)

    # Total return = (ending equity / starting equity - 1) * 100.
    strategy_return = (strategy_equity.iloc[-1] / strategy_equity.iloc[0] - 1) * 100
    buy_hold_return = (buy_hold_equity.iloc[-1] / buy_hold_equity.iloc[0] - 1) * 100

    # Drawdown = (equity / prior peak equity - 1) * 100; report the deepest loss.
    drawdown = (strategy_equity / strategy_equity.cummax() - 1) * 100
    max_drawdown = drawdown.min()

    # Win rate = winning trades / total trades * 100.
    win_rate = winning_trades / trade_count * 100 if trade_count else 0
    average_trade_profit = (
        sum(trade["ProfitPct"] for trade in trades) / trade_count
        if trade_count
        else 0
    )
    daily_strategy_returns = strategy_equity.pct_change().dropna()
    daily_buy_hold_returns = buy_hold_equity.pct_change().dropna()
    strategy_return_periods = len(daily_strategy_returns)
    buy_hold_return_periods = len(daily_buy_hold_returns)
    if strategy_return_periods:
        strategy_annualized_return = (
            (strategy_equity.iloc[-1] / strategy_equity.iloc[0])
            ** (252 / strategy_return_periods)
            - 1
        ) * 100
    else:
        strategy_annualized_return = 0
    if buy_hold_return_periods:
        buy_hold_annualized_return = (
            (buy_hold_equity.iloc[-1] / buy_hold_equity.iloc[0])
            ** (252 / buy_hold_return_periods)
            - 1
        ) * 100
    else:
        buy_hold_annualized_return = 0
    daily_volatility = daily_strategy_returns.std()
    annualized_sharpe_ratio = (
        daily_strategy_returns.mean() / daily_volatility * (252 ** 0.5)
        if pd.notna(daily_volatility) and daily_volatility > 0
        else 0
    )

    winning_profits = [
        trade["ProfitPct"] for trade in trades if trade["ProfitPct"] > 0
    ]
    losing_profits = [
        trade["ProfitPct"] for trade in trades if trade["ProfitPct"] < 0
    ]
    profit_loss_ratio = (
        (sum(winning_profits) / len(winning_profits))
        / abs(sum(losing_profits) / len(losing_profits))
        if winning_profits and losing_profits
        else None
    )

    return {
        "strategy_total_return_pct": strategy_return,
        "buy_hold_total_return_pct": buy_hold_return,
        "max_drawdown_pct": max_drawdown,
        "number_of_trades": trade_count,
        "winning_trades": winning_trades,
        "win_rate_pct": win_rate,
        "average_trade_profit_pct": average_trade_profit,
        "annualized_sharpe_ratio": annualized_sharpe_ratio,
        "profit_loss_ratio": profit_loss_ratio,
        "strategy_annualized_return_pct": strategy_annualized_return,
        "buy_hold_annualized_return_pct": buy_hold_annualized_return,
    }

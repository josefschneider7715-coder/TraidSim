from __future__ import annotations

import numpy as np
import pandas as pd


def backtest(
    df: pd.DataFrame,
    initial_capital: float = 10_000.0,
    risk_per_trade: float = 0.01,
    atr_stop_factor: float = 2.0,
    atr_take_profit_factor: float = 3.0,
    trading_fee: float = 0.001,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = df.copy().reset_index(drop=True)
    cash = initial_capital
    position = 0.0
    entry_price = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    trades = []
    equity_curve = []

    for i in range(1, len(result)):
        today = result.iloc[i]
        yesterday = result.iloc[i - 1]
        date = today["Date"]
        open_price = float(today["Open"])
        high_price = float(today["High"])
        low_price = float(today["Low"])
        close_price = float(today["Close"])

        if position > 0:
            exit_price = None
            exit_reason = None

            if low_price <= stop_loss:
                exit_price = stop_loss
                exit_reason = "Stop-Loss"
            elif high_price >= take_profit:
                exit_price = take_profit
                exit_reason = "Take-Profit"
            elif bool(yesterday["EXIT_SIGNAL"]):
                exit_price = open_price
                exit_reason = "Exit-Signal"

            if exit_price is not None:
                gross_value = position * exit_price
                fee = gross_value * trading_fee
                cash += gross_value - fee
                profit = (exit_price - entry_price) * position - fee
                trades.append(
                    {
                        "Date": date,
                        "Type": "SELL",
                        "Price": exit_price,
                        "Units": position,
                        "Profit": profit,
                        "Reason": exit_reason,
                        "Cash": cash,
                        "Equity": cash,
                    }
                )
                position = 0.0
                entry_price = 0.0
                stop_loss = 0.0
                take_profit = 0.0

        if position == 0 and bool(yesterday["ENTRY_SIGNAL"]):
            atr_value = float(yesterday["ATR"])

            if not np.isnan(atr_value) and atr_value > 0:
                entry_price = open_price
                stop_loss = entry_price - atr_stop_factor * atr_value
                take_profit = entry_price + atr_take_profit_factor * atr_value
                risk_amount = cash * risk_per_trade
                risk_per_unit = entry_price - stop_loss

                if risk_per_unit > 0:
                    units = min(risk_amount / risk_per_unit, cash / entry_price)
                    buy_value = units * entry_price
                    fee = buy_value * trading_fee

                    if units > 0 and cash >= buy_value + fee:
                        cash -= buy_value + fee
                        position = units
                        trades.append(
                            {
                                "Date": date,
                                "Type": "BUY",
                                "Price": entry_price,
                                "Units": position,
                                "Profit": 0.0,
                                "Reason": "Entry-Signal",
                                "Cash": cash,
                                "Stop_Loss": stop_loss,
                                "Take_Profit": take_profit,
                            }
                        )

        equity_curve.append(
            {
                "Date": date,
                "Equity": cash + position * close_price,
                "Cash": cash,
                "Position_Value": position * close_price,
                "Close": close_price,
            }
        )

    return pd.DataFrame(trades), pd.DataFrame(equity_curve)


def calculate_metrics(trades_df: pd.DataFrame, equity_df: pd.DataFrame, initial_capital: float) -> dict:
    if equity_df.empty:
        return {}

    final_equity = float(equity_df["Equity"].iloc[-1])
    total_return_pct = (final_equity / initial_capital - 1) * 100
    equity = equity_df["Equity"]
    drawdown = (equity - equity.cummax()) / equity.cummax()
    sells = trades_df[trades_df["Type"] == "SELL"] if not trades_df.empty else pd.DataFrame()

    metrics = {
        "Startkapital": initial_capital,
        "Endkapital": final_equity,
        "Gesamtrendite %": total_return_pct,
        "Max. Drawdown %": float(drawdown.min() * 100),
        "Abgeschlossene Trades": int(len(sells)),
        "Trefferquote %": 0.0,
        "Gewinnsumme": 0.0,
        "Durchschnitt Trade": 0.0,
    }

    if sells.empty:
        return metrics

    wins = sells[sells["Profit"] > 0]
    metrics.update(
        {
            "Trefferquote %": len(wins) / len(sells) * 100,
            "Gewinnsumme": float(sells["Profit"].sum()),
            "Durchschnitt Trade": float(sells["Profit"].mean()),
            "Bester Trade": float(sells["Profit"].max()),
            "Schlechtester Trade": float(sells["Profit"].min()),
        }
    )
    return metrics


def buy_and_hold_metrics(df: pd.DataFrame, initial_capital: float = 10_000.0) -> dict:
    clean = df.dropna().reset_index(drop=True)

    if clean.empty:
        return {}

    start_price = float(clean.iloc[0]["Close"])
    end_price = float(clean.iloc[-1]["Close"])
    units = initial_capital / start_price
    final_equity = units * end_price
    equity_curve = clean["Close"] * units
    drawdown = (equity_curve - equity_curve.cummax()) / equity_curve.cummax()

    return {
        "BuyHold Startkapital": initial_capital,
        "BuyHold Endkapital": final_equity,
        "BuyHold Rendite %": (final_equity / initial_capital - 1) * 100,
        "BuyHold Max. Drawdown %": float(drawdown.min() * 100),
    }

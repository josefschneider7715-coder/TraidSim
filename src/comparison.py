from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


PositionMode = Literal["risk", "full_capital"]


@dataclass(frozen=True)
class BenchmarkResult:
    """Ein einheitliches Ergebnis fuer Strategie- und Vergleichsrechnungen."""

    equity: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict[str, float | int | str]


_REQUIRED_PRICE_COLUMNS = {"Date", "Open", "High", "Low", "Close"}


def _prepare_prices(df: pd.DataFrame) -> pd.DataFrame:
    missing = _REQUIRED_PRICE_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Fehlende Kursfelder: {', '.join(sorted(missing))}")

    clean = df.copy()
    clean["Date"] = pd.to_datetime(clean["Date"], errors="coerce")
    for column in ["Open", "High", "Low", "Close"]:
        clean[column] = pd.to_numeric(clean[column], errors="coerce")

    clean = clean.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    clean = clean[(clean[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
    clean = clean.sort_values("Date").drop_duplicates("Date", keep="last").reset_index(drop=True)
    return clean


def _empty_result(initial_capital: float, label: str) -> BenchmarkResult:
    metrics = {
        "Variante": label,
        "Startkapital": float(initial_capital),
        "Endkapital": float(initial_capital),
        "Gesamtrendite %": 0.0,
        "Max. Drawdown %": 0.0,
        "Abgeschlossene Trades": 0,
        "Gebuehren gesamt": 0.0,
        "Marktzeit %": 0.0,
    }
    return BenchmarkResult(pd.DataFrame(columns=["Date", "Equity"]), pd.DataFrame(), metrics)


def _curve_metrics(
    equity_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    initial_capital: float,
    fees_total: float,
    exposure_pct: float,
    label: str,
) -> dict[str, float | int | str]:
    if equity_df.empty:
        return _empty_result(initial_capital, label).metrics

    equity = pd.to_numeric(equity_df["Equity"], errors="coerce").dropna()
    if equity.empty:
        return _empty_result(initial_capital, label).metrics

    final_equity = float(equity.iloc[-1])
    running_max = equity.cummax().replace(0, np.nan)
    drawdown = (equity - running_max) / running_max
    completed_trades = 0
    if not trades_df.empty and "Type" in trades_df.columns:
        completed_trades = int((trades_df["Type"] == "SELL").sum())

    return {
        "Variante": label,
        "Startkapital": float(initial_capital),
        "Endkapital": final_equity,
        "Gesamtrendite %": (final_equity / initial_capital - 1.0) * 100.0 if initial_capital else 0.0,
        "Max. Drawdown %": float(drawdown.min() * 100.0) if not drawdown.empty else 0.0,
        "Abgeschlossene Trades": completed_trades,
        "Gebuehren gesamt": float(fees_total),
        "Marktzeit %": float(exposure_pct),
    }


def run_strategy_benchmark(
    df: pd.DataFrame,
    initial_capital: float = 10_000.0,
    risk_per_trade: float = 0.01,
    atr_stop_factor: float = 2.0,
    atr_take_profit_factor: float = 3.0,
    trading_fee: float = 0.001,
    position_mode: PositionMode = "risk",
) -> BenchmarkResult:
    """Berechnet die DayTrade-Lab-Strategie und liquidiert offene Positionen am Ende.

    Die Signale des Vortags werden wie im bestehenden Backtest am naechsten
    Eroeffnungskurs ausgefuehrt. Stop-Loss und Take-Profit verwenden Tageshoch
    und Tagestief. Bei gleichzeitig beruehrtem Stop und Ziel gilt konservativ
    zuerst der Stop-Loss.
    """

    if initial_capital <= 0:
        raise ValueError("Das Startkapital muss groesser als null sein.")
    if not 0 <= trading_fee < 1:
        raise ValueError("Die Gebuehr muss zwischen 0 und 1 liegen.")
    if position_mode not in {"risk", "full_capital"}:
        raise ValueError("Unbekannter Positionsmodus.")

    result = _prepare_prices(df)
    if len(result) < 2:
        return _empty_result(initial_capital, "DayTrade-Lab-Strategie")

    if "ENTRY_SIGNAL" not in result.columns:
        result["ENTRY_SIGNAL"] = False
    if "EXIT_SIGNAL" not in result.columns:
        result["EXIT_SIGNAL"] = False
    if "ATR" not in result.columns:
        result["ATR"] = np.nan

    result["ENTRY_SIGNAL"] = result["ENTRY_SIGNAL"].fillna(False).astype(bool)
    result["EXIT_SIGNAL"] = result["EXIT_SIGNAL"].fillna(False).astype(bool)
    result["ATR"] = pd.to_numeric(result["ATR"], errors="coerce")

    cash = float(initial_capital)
    position = 0.0
    entry_price = 0.0
    entry_fee = 0.0
    entry_date = None
    stop_loss = 0.0
    take_profit = 0.0
    fees_total = 0.0
    exposure_rows = 0
    trades: list[dict] = []
    equity_rows: list[dict] = [
        {
            "Date": result.iloc[0]["Date"],
            "Equity": cash,
            "Cash": cash,
            "Position_Value": 0.0,
            "Close": float(result.iloc[0]["Close"]),
        }
    ]

    for i in range(1, len(result)):
        today = result.iloc[i]
        yesterday = result.iloc[i - 1]
        date = today["Date"]
        open_price = float(today["Open"])
        high_price = float(today["High"])
        low_price = float(today["Low"])
        close_price = float(today["Close"])

        if position > 0:
            exit_price: float | None = None
            exit_reason: str | None = None
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
                exit_fee = gross_value * trading_fee
                fees_total += exit_fee
                cash += gross_value - exit_fee
                profit = (exit_price - entry_price) * position - entry_fee - exit_fee
                trades.append(
                    {
                        "Date": date,
                        "Type": "SELL",
                        "Price": exit_price,
                        "Units": position,
                        "Profit": profit,
                        "Reason": exit_reason,
                        "Cash": cash,
                        "Entry_Date": entry_date,
                    }
                )
                position = 0.0
                entry_price = 0.0
                entry_fee = 0.0
                entry_date = None
                stop_loss = 0.0
                take_profit = 0.0

        if position == 0 and bool(yesterday["ENTRY_SIGNAL"]):
            atr_value = float(yesterday["ATR"])
            if np.isfinite(atr_value) and atr_value > 0:
                candidate_stop = open_price - atr_stop_factor * atr_value
                candidate_take_profit = open_price + atr_take_profit_factor * atr_value
                risk_per_unit = open_price - candidate_stop

                if risk_per_unit > 0:
                    affordable_units = cash / (open_price * (1.0 + trading_fee))
                    if position_mode == "full_capital":
                        units = affordable_units
                    else:
                        risk_amount = cash * risk_per_trade
                        units = min(risk_amount / risk_per_unit, affordable_units)

                    if units > 0:
                        buy_value = units * open_price
                        buy_fee = buy_value * trading_fee
                        total_cost = buy_value + buy_fee
                        if cash + 1e-9 >= total_cost:
                            cash -= total_cost
                            position = units
                            entry_price = open_price
                            entry_fee = buy_fee
                            entry_date = date
                            stop_loss = candidate_stop
                            take_profit = candidate_take_profit
                            fees_total += buy_fee
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

        if position > 0:
            exposure_rows += 1

        equity_rows.append(
            {
                "Date": date,
                "Equity": cash + position * close_price,
                "Cash": cash,
                "Position_Value": position * close_price,
                "Close": close_price,
            }
        )

    if position > 0:
        last = result.iloc[-1]
        exit_price = float(last["Close"])
        gross_value = position * exit_price
        exit_fee = gross_value * trading_fee
        fees_total += exit_fee
        cash += gross_value - exit_fee
        profit = (exit_price - entry_price) * position - entry_fee - exit_fee
        trades.append(
            {
                "Date": last["Date"],
                "Type": "SELL",
                "Price": exit_price,
                "Units": position,
                "Profit": profit,
                "Reason": "Ende Zeitfenster",
                "Cash": cash,
                "Entry_Date": entry_date,
            }
        )
        position = 0.0
        equity_rows[-1]["Equity"] = cash
        equity_rows[-1]["Cash"] = cash
        equity_rows[-1]["Position_Value"] = 0.0

    equity_df = pd.DataFrame(equity_rows)
    trades_df = pd.DataFrame(trades)
    exposure_pct = exposure_rows / len(result) * 100.0
    label = "DayTrade-Lab-Strategie (100 % Kapital)" if position_mode == "full_capital" else "DayTrade-Lab-Strategie (Risikomodell)"
    metrics = _curve_metrics(equity_df, trades_df, initial_capital, fees_total, exposure_pct, label)
    return BenchmarkResult(equity_df, trades_df, metrics)


def run_buy_and_hold_benchmark(
    df: pd.DataFrame,
    initial_capital: float = 10_000.0,
    trading_fee: float = 0.001,
) -> BenchmarkResult:
    """Kauft am ersten Open, verkauft am letzten Close und zieht beide Gebuehren ab."""

    if initial_capital <= 0:
        raise ValueError("Das Startkapital muss groesser als null sein.")
    if not 0 <= trading_fee < 1:
        raise ValueError("Die Gebuehr muss zwischen 0 und 1 liegen.")

    prices = _prepare_prices(df)
    if len(prices) < 2:
        return _empty_result(initial_capital, "Buy and Hold")

    first = prices.iloc[0]
    last = prices.iloc[-1]
    entry_price = float(first["Open"])
    units = initial_capital / (entry_price * (1.0 + trading_fee))
    buy_value = units * entry_price
    buy_fee = buy_value * trading_fee

    equity_rows = []
    for i, row in prices.iterrows():
        equity_value = units * float(row["Close"])
        if i == len(prices) - 1:
            equity_value *= 1.0 - trading_fee
        equity_rows.append(
            {
                "Date": row["Date"],
                "Equity": equity_value,
                "Cash": 0.0 if i < len(prices) - 1 else equity_value,
                "Position_Value": equity_value if i < len(prices) - 1 else 0.0,
                "Close": float(row["Close"]),
            }
        )

    gross_exit = units * float(last["Close"])
    sell_fee = gross_exit * trading_fee
    final_cash = gross_exit - sell_fee
    profit = final_cash - initial_capital
    trades_df = pd.DataFrame(
        [
            {
                "Date": first["Date"],
                "Type": "BUY",
                "Price": entry_price,
                "Units": units,
                "Profit": 0.0,
                "Reason": "Beginn Zeitfenster",
                "Cash": 0.0,
                "Fee": buy_fee,
            },
            {
                "Date": last["Date"],
                "Type": "SELL",
                "Price": float(last["Close"]),
                "Units": units,
                "Profit": profit,
                "Reason": "Ende Zeitfenster",
                "Cash": final_cash,
                "Fee": sell_fee,
            },
        ]
    )
    equity_df = pd.DataFrame(equity_rows)
    fees_total = buy_fee + sell_fee
    metrics = _curve_metrics(equity_df, trades_df, initial_capital, fees_total, 100.0, "Buy and Hold")
    return BenchmarkResult(equity_df, trades_df, metrics)


def run_oracle_benchmark(
    df: pd.DataFrame,
    initial_capital: float = 10_000.0,
    trading_fee: float = 0.001,
) -> BenchmarkResult:
    """Theoretische Long-only-Obergrenze auf Schlusskursbasis.

    Dynamische Programmierung findet die kapitalmaximierende Folge aus
    nicht ueberlappenden All-in-Kaeufen und -Verkaeufen. Das Oracle kennt alle
    spaeteren Schlusskurse. Es ist deshalb ausdruecklich nicht real handelbar.
    """

    if initial_capital <= 0:
        raise ValueError("Das Startkapital muss groesser als null sein.")
    if not 0 <= trading_fee < 1:
        raise ValueError("Die Gebuehr muss zwischen 0 und 1 liegen.")

    prices = _prepare_prices(df)
    if len(prices) < 2:
        return _empty_result(initial_capital, "Oracle (Schlusskursbasis)")

    close = prices["Close"].to_numpy(dtype=float)
    n = len(close)
    cash = np.empty(n, dtype=float)
    units = np.empty(n, dtype=float)
    cash_from = np.full(n, "cash", dtype=object)
    units_from = np.full(n, "hold", dtype=object)

    cash[0] = initial_capital
    units[0] = initial_capital / (close[0] * (1.0 + trading_fee))
    units_from[0] = "cash"
    eps = 1e-12

    for i in range(1, n):
        sell_candidate = units[i - 1] * close[i] * (1.0 - trading_fee)
        if sell_candidate > cash[i - 1] + eps:
            cash[i] = sell_candidate
            cash_from[i] = "hold"
        else:
            cash[i] = cash[i - 1]
            cash_from[i] = "cash"

        buy_candidate = cash[i - 1] / (close[i] * (1.0 + trading_fee))
        if buy_candidate > units[i - 1] + eps:
            units[i] = buy_candidate
            units_from[i] = "cash"
        else:
            units[i] = units[i - 1]
            units_from[i] = "hold"

    actions: list[tuple[int, str]] = []
    state = "cash"
    i = n - 1
    while i >= 0:
        if state == "cash":
            if i > 0 and cash_from[i] == "hold":
                actions.append((i, "SELL"))
                state = "hold"
            i -= 1
        else:
            if i == 0:
                actions.append((0, "BUY"))
                break
            if units_from[i] == "cash":
                actions.append((i, "BUY"))
                state = "cash"
            i -= 1

    actions.sort(key=lambda item: item[0])
    action_by_index = {index: action for index, action in actions}

    replay_cash = float(initial_capital)
    replay_units = 0.0
    fees_total = 0.0
    exposure_rows = 0
    trade_rows: list[dict] = []
    equity_rows: list[dict] = []
    entry_price = 0.0
    entry_fee = 0.0
    entry_date = None

    for index, row in prices.iterrows():
        price = float(row["Close"])
        action = action_by_index.get(index)

        if action == "BUY" and replay_units == 0:
            replay_units = replay_cash / (price * (1.0 + trading_fee))
            buy_value = replay_units * price
            entry_fee = buy_value * trading_fee
            fees_total += entry_fee
            replay_cash -= buy_value + entry_fee
            if abs(replay_cash) < 1e-8:
                replay_cash = 0.0
            entry_price = price
            entry_date = row["Date"]
            trade_rows.append(
                {
                    "Date": row["Date"],
                    "Type": "BUY",
                    "Price": price,
                    "Units": replay_units,
                    "Profit": 0.0,
                    "Reason": "Oracle-Kauf",
                    "Cash": replay_cash,
                    "Fee": entry_fee,
                }
            )
        elif action == "SELL" and replay_units > 0:
            gross_value = replay_units * price
            sell_fee = gross_value * trading_fee
            fees_total += sell_fee
            replay_cash += gross_value - sell_fee
            profit = (price - entry_price) * replay_units - entry_fee - sell_fee
            trade_rows.append(
                {
                    "Date": row["Date"],
                    "Type": "SELL",
                    "Price": price,
                    "Units": replay_units,
                    "Profit": profit,
                    "Reason": "Oracle-Verkauf",
                    "Cash": replay_cash,
                    "Fee": sell_fee,
                    "Entry_Date": entry_date,
                }
            )
            replay_units = 0.0
            entry_price = 0.0
            entry_fee = 0.0
            entry_date = None

        if replay_units > 0:
            exposure_rows += 1

        equity_rows.append(
            {
                "Date": row["Date"],
                "Equity": replay_cash + replay_units * price,
                "Cash": replay_cash,
                "Position_Value": replay_units * price,
                "Close": price,
            }
        )

    equity_df = pd.DataFrame(equity_rows)
    trades_df = pd.DataFrame(trade_rows)
    exposure_pct = exposure_rows / n * 100.0
    metrics = _curve_metrics(
        equity_df,
        trades_df,
        initial_capital,
        fees_total,
        exposure_pct,
        "Theoretisches Optimum (Oracle, Schlusskursbasis)",
    )
    return BenchmarkResult(equity_df, trades_df, metrics)


def align_equity_curves(
    strategy: BenchmarkResult,
    buy_hold: BenchmarkResult,
    oracle: BenchmarkResult,
) -> pd.DataFrame:
    """Richtet alle Kapitalverlaeufe auf identische Datumswerte aus."""

    def curve(result: BenchmarkResult, column_name: str) -> pd.DataFrame:
        if result.equity.empty:
            return pd.DataFrame(columns=["Date", column_name])
        frame = result.equity[["Date", "Equity"]].copy()
        frame["Date"] = pd.to_datetime(frame["Date"])
        return frame.rename(columns={"Equity": column_name})

    aligned = curve(strategy, "Strategie")
    aligned = aligned.merge(curve(buy_hold, "Buy and Hold"), on="Date", how="outer")
    aligned = aligned.merge(curve(oracle, "Oracle"), on="Date", how="outer")
    aligned = aligned.sort_values("Date").reset_index(drop=True)
    for column in ["Strategie", "Buy and Hold", "Oracle"]:
        aligned[column] = aligned[column].ffill().bfill()
    aligned["Vorteil Strategie"] = aligned["Strategie"] - aligned["Buy and Hold"]
    return aligned


def comparison_metrics(
    strategy: BenchmarkResult,
    buy_hold: BenchmarkResult,
    oracle: BenchmarkResult,
    initial_capital: float,
) -> dict[str, float]:
    strategy_end = float(strategy.metrics.get("Endkapital", initial_capital))
    buy_hold_end = float(buy_hold.metrics.get("Endkapital", initial_capital))
    oracle_end = float(oracle.metrics.get("Endkapital", initial_capital))

    advantage_eur = strategy_end - buy_hold_end
    advantage_pct = (strategy_end / buy_hold_end - 1.0) * 100.0 if buy_hold_end else 0.0
    oracle_gap_eur = oracle_end - strategy_end
    oracle_gap_pct = (1.0 - strategy_end / oracle_end) * 100.0 if oracle_end else 0.0
    theoretical_profit = oracle_end - initial_capital
    achieved_potential_pct = (
        (strategy_end - initial_capital) / theoretical_profit * 100.0 if theoretical_profit > 0 else 0.0
    )

    return {
        "Vorteil Strategie EUR": advantage_eur,
        "Vorteil Strategie %": advantage_pct,
        "Abstand zum Oracle EUR": oracle_gap_eur,
        "Abstand zum Oracle %": oracle_gap_pct,
        "Erreichtes theoretisches Potenzial %": achieved_potential_pct,
    }

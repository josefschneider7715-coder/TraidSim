from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PaperAccount:
    initial_capital: float
    cash: float
    symbol: str | None = None
    quantity: int = 0
    entry_price: float = 0.0
    stop_price: float = 0.0
    take_profit_price: float = 0.0
    entry_fee: float = 0.0
    last_processed_candle: str = ""
    trades: list[dict] = field(default_factory=list)

    @classmethod
    def create(cls, initial_capital: float) -> "PaperAccount":
        return cls(initial_capital=float(initial_capital), cash=float(initial_capital))

    def equity(self, current_price: float) -> float:
        return self.cash + self.quantity * float(current_price)


def open_virtual_position(
    account: PaperAccount, *, symbol: str, price: float, atr: float,
    trade_amount: float, fee_fraction: float, stop_factor: float, take_profit_factor: float,
) -> str:
    if account.quantity > 0:
        return "Es besteht bereits eine virtuelle Position"
    quantity = math.floor(min(account.cash, trade_amount) / (price * (1 + fee_fraction)))
    if quantity <= 0:
        return "Einsatzsumme reicht nicht für eine ganze Aktie"
    cost = quantity * price
    entry_fee = cost * fee_fraction
    account.cash -= cost + entry_fee
    account.symbol = symbol
    account.quantity = quantity
    account.entry_price = price
    account.entry_fee = entry_fee
    account.stop_price = price - atr * stop_factor
    account.take_profit_price = price + atr * take_profit_factor
    account.trades.append({
        "Zeit": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Symbol": symbol,
        "Aktion": "KAUF", "Stück": quantity, "Kurs": price,
        "Gebühr": entry_fee, "Gewinn/Verlust": 0.0, "Grund": "Manuell angelegte virtuelle Startposition",
    })
    return f"Virtuelle Startposition eröffnet: {quantity} Stück"


def process_virtual_order(
    account: PaperAccount,
    *,
    symbol: str,
    signal: str,
    price: float,
    atr: float,
    candle_id: str,
    trade_amount: float,
    risk_fraction: float,
    fee_fraction: float,
    stop_factor: float,
    take_profit_factor: float,
) -> str:
    if candle_id == account.last_processed_candle:
        return "Keine neue Kerze"
    account.last_processed_candle = candle_id

    if account.quantity > 0 and account.symbol != symbol:
        return f"Offene Position in {account.symbol}; zur Überwachung dieses Symbol auswählen"

    if account.quantity > 0:
        exit_reason = None
        if price <= account.stop_price:
            exit_reason = "Stop-Loss"
        elif price >= account.take_profit_price:
            exit_reason = "Take-Profit"
        elif signal == "VERKAUFEN":
            exit_reason = "Verkaufssignal"
        if exit_reason:
            proceeds = account.quantity * price
            exit_fee = proceeds * fee_fraction
            pnl = proceeds - exit_fee - account.quantity * account.entry_price - account.entry_fee
            account.cash += proceeds - exit_fee
            account.trades.append({
                "Zeit": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Symbol": account.symbol,
                "Aktion": "VERKAUF", "Stück": account.quantity, "Kurs": price,
                "Gebühr": exit_fee, "Gewinn/Verlust": pnl, "Grund": exit_reason,
            })
            account.symbol = None
            account.quantity = 0
            account.entry_price = account.stop_price = account.take_profit_price = account.entry_fee = 0.0
            return exit_reason

    if account.quantity == 0 and signal == "KAUFEN" and atr > 0:
        risk_budget = min(account.initial_capital, trade_amount) * risk_fraction
        risk_per_share = atr * stop_factor
        by_risk = math.floor(risk_budget / risk_per_share) if risk_per_share > 0 else 0
        by_capital = math.floor(min(account.cash, trade_amount) / (price * (1 + fee_fraction)))
        quantity = max(0, min(by_risk, by_capital))
        if quantity == 0:
            return "Kein Kauf: Einsatz oder Risikobudget zu klein"
        cost = quantity * price
        entry_fee = cost * fee_fraction
        account.cash -= cost + entry_fee
        account.symbol = symbol
        account.quantity = quantity
        account.entry_price = price
        account.entry_fee = entry_fee
        account.stop_price = price - atr * stop_factor
        account.take_profit_price = price + atr * take_profit_factor
        account.trades.append({
            "Zeit": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Symbol": symbol,
            "Aktion": "KAUF", "Stück": quantity, "Kurs": price,
            "Gebühr": entry_fee, "Gewinn/Verlust": 0.0, "Grund": "Automatisches Kaufsignal",
        })
        return "Virtueller Kauf ausgeführt"
    return "Keine Order"

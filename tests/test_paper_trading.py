from src.paper_trading import PaperAccount, open_virtual_position, process_virtual_order


def test_virtual_buy_and_take_profit() -> None:
    account = PaperAccount.create(10_000)
    result = process_virtual_order(account, symbol="TEST", signal="KAUFEN", price=100, atr=2, candle_id="1", trade_amount=5_000, risk_fraction=.01, fee_fraction=.001, stop_factor=2, take_profit_factor=3)
    assert result == "Virtueller Kauf ausgeführt"
    assert account.quantity > 0
    result = process_virtual_order(account, symbol="TEST", signal="BEOBACHTEN", price=106, atr=2, candle_id="2", trade_amount=5_000, risk_fraction=.01, fee_fraction=.001, stop_factor=2, take_profit_factor=3)
    assert result == "Take-Profit"
    assert account.quantity == 0
    assert len(account.trades) == 2


def test_manual_virtual_start_position_uses_trade_amount() -> None:
    account = PaperAccount.create(10_000)
    result = open_virtual_position(account, symbol="TEST", price=100, atr=2, trade_amount=5_000, fee_fraction=.001, stop_factor=2, take_profit_factor=3)
    assert "eröffnet" in result
    assert account.quantity == 49
    assert account.stop_price == 96
    assert account.take_profit_price == 106

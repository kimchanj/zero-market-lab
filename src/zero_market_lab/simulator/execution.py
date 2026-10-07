"""Reusable limit-touch execution and explicit trading-cost policies."""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_UP

from .models import CostConfig, Instrument


def quantize_money(value: Decimal, precision: int) -> Decimal:
    quantum = Decimal(1).scaleb(-precision)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def floor_to_tick(value: Decimal, tick: Decimal) -> Decimal:
    return (value / tick).to_integral_value(rounding=ROUND_FLOOR) * tick


def ceil_to_tick(value: Decimal, tick: Decimal) -> Decimal:
    return (value / tick).to_integral_value(rounding=ROUND_CEILING) * tick


class ConfigurableFeeModel:
    def __init__(self, config: CostConfig, currency_precision: int):
        self.config = config
        self.currency_precision = currency_precision

    def buy_fee(self, notional: Decimal) -> Decimal:
        return quantize_money(
            notional * self.config.buy_fee_rate + self.config.fixed_buy_fee,
            self.currency_precision,
        )

    def sell_fee(self, notional: Decimal) -> Decimal:
        return quantize_money(
            notional * self.config.sell_fee_rate + self.config.fixed_sell_fee,
            self.currency_precision,
        )

    def tax(self, notional: Decimal) -> Decimal:
        return quantize_money(notional * self.config.sell_tax_rate, self.currency_precision)


class LimitTouchExecutionModel:
    def __init__(self, instrument: Instrument, fee_model: ConfigurableFeeModel):
        self.instrument = instrument
        self.fees = fee_model

    def entry_limit(self, open_price: Decimal, offset_rate: Decimal) -> Decimal:
        return floor_to_tick(open_price * (Decimal("1") - offset_rate), self.instrument.tick_size)

    def take_profit_limit(self, average_price: Decimal, rate: Decimal) -> Decimal:
        return ceil_to_tick(average_price * (Decimal("1") + rate), self.instrument.tick_size)

    def quantity_for_cash(self, cash: Decimal, price: Decimal) -> Decimal:
        if price <= 0 or cash <= 0:
            return Decimal("0")
        estimate = cash / (price * (Decimal("1") + self.fees.config.buy_fee_rate))
        if self.instrument.fractional_allowed:
            quantum = Decimal(1).scaleb(-self.instrument.quantity_precision)
            quantity = estimate.quantize(quantum, rounding=ROUND_DOWN)
        else:
            lots = (estimate / self.instrument.lot_size).to_integral_value(rounding=ROUND_FLOOR)
            quantity = lots * self.instrument.lot_size
        while quantity > 0:
            notional = quantity * price
            if notional + self.fees.buy_fee(notional) <= cash:
                return quantity
            quantity -= self.instrument.lot_size if not self.instrument.fractional_allowed else quantum
        return Decimal("0")


def required_exit_price(
    *,
    entry_price: Decimal,
    quantity: Decimal,
    buy_fee: Decimal,
    minimum_net_return: Decimal,
    instrument: Instrument,
    costs: CostConfig,
) -> Decimal:
    """Minimum tick-aligned exit price meeting a net-return threshold."""

    if quantity <= 0:
        raise ValueError("quantity must be positive")
    denominator = quantity * (Decimal("1") - costs.sell_fee_rate - costs.sell_tax_rate)
    if denominator <= 0:
        raise ValueError("sell fee and tax rates leave no sale proceeds")
    invested = entry_price * quantity + buy_fee
    raw = invested * (Decimal("1") + minimum_net_return) / denominator
    candidate = ceil_to_tick(raw, instrument.tick_size)
    fees = ConfigurableFeeModel(costs, instrument.currency_precision)
    while True:
        proceeds = candidate * quantity
        net_profit = proceeds - fees.sell_fee(proceeds) - fees.tax(proceeds) - invested
        if net_profit / invested >= minimum_net_return:
            return candidate
        candidate += instrument.tick_size

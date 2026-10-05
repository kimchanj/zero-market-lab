"""Cash, position and weighted-average-cost accounting."""

from dataclasses import dataclass
import math


@dataclass
class Portfolio:
    cash: float = 0.0
    quantity: float = 0.0
    average_purchase_price: float | None = None
    total_contribution: float = 0.0

    def contribute(self, amount: float) -> None:
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("Contribution must be finite and > 0")
        self.cash += amount
        self.total_contribution += amount

    def buy_all(self, price: float) -> tuple[float, float]:
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Buy price must be finite and > 0")
        if self.cash <= 0:
            return 0.0, 0.0

        amount = self.cash
        buy_quantity = amount / price
        old_cost = self.quantity * (self.average_purchase_price or 0.0)
        new_quantity = self.quantity + buy_quantity
        self.average_purchase_price = (old_cost + buy_quantity * price) / new_quantity
        self.quantity = new_quantity
        self.cash = 0.0
        return buy_quantity, amount

    def value(self, market_price: float) -> tuple[float, float]:
        if not math.isfinite(market_price) or market_price <= 0:
            raise ValueError("Market price must be finite and > 0")
        position_value = self.quantity * market_price
        return position_value, self.cash + position_value

    def sell_all(self, price: float) -> tuple[float, float]:
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Sell price must be finite and > 0")
        sold_quantity = self.quantity
        proceeds = sold_quantity * price
        self.cash += proceeds
        self.quantity = 0.0
        self.average_purchase_price = None
        return sold_quantity, proceeds

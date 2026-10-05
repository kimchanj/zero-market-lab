"""Strategy A: invest available cash and never sell."""


class BuyAndHoldStrategy:
    name = "MONTHLY_BUY_AND_HOLD"

    @staticmethod
    def wants_buy(available_cash: float) -> bool:
        return available_cash > 0

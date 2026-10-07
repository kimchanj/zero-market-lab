"""Korean presentation text derived only from structured decisions."""

from __future__ import annotations

from decimal import Decimal

from .models import DecisionRecord, DailyLedgerRow


def _money(value: Decimal | str | None) -> str:
    if value is None or isinstance(value, str):
        return "—" if value is None else value
    return f"{value:,.8f}".rstrip("0").rstrip(".")


def explain_decisions(decisions: list[DecisionRecord]) -> str:
    parts: list[str] = []
    for decision in decisions:
        if decision.reason_code == "ENTRY_FILLED":
            parts.append(
                f"시가 기준 지정가를 {_money(decision.rule_value)}으로 설정했습니다. "
                f"당일 저가가 {_money(decision.observed_value)}으로 지정가 이하라 매수 체결되었습니다."
            )
        elif decision.reason_code == "ENTRY_NOT_TOUCHED":
            parts.append(
                f"매수 지정가는 {_money(decision.rule_value)}입니다. 당일 저가 "
                f"{_money(decision.observed_value)}이 더 높아 체결되지 않았습니다."
            )
        elif decision.reason_code == "INSUFFICIENT_CASH":
            parts.append("지정가에 최소 거래단위를 살 현금이 부족해 주문이 체결되지 않았습니다.")
        elif decision.reason_code == "TARGET_NOT_REACHED":
            gap = Decimal(str(decision.rule_value)) - Decimal(str(decision.observed_value))
            parts.append(
                f"익절 목표가는 {_money(decision.rule_value)}입니다. 오늘 고가는 "
                f"{_money(decision.observed_value)}이며 목표보다 {_money(gap)} 낮아 보유를 유지합니다."
            )
        elif decision.reason_code == "TAKE_PROFIT_FILLED":
            parts.append(
                f"오늘 고가 {_money(decision.observed_value)}이 익절 지정가 "
                f"{_money(decision.rule_value)}에 도달해 지정가로 매도 체결되었습니다."
            )
        elif decision.reason_code == "AMBIGUOUS_ENTRY_EXIT":
            parts.append(
                "같은 일봉에서 매수와 익절 조건이 모두 관측됐지만 발생 순서를 알 수 없습니다. "
                "보수적으로 당일 매도하지 않고 포지션을 유지합니다."
            )
        elif decision.reason_code == "NEXT_BAR_REENTRY":
            parts.append("직전 거래일 매도 후 정책에 따라 다음 거래일부터 새 진입 주문을 평가합니다.")
    return " ".join(parts)


def explain_ledger_row(row: DailyLedgerRow, currency: str) -> str:
    """Presentation only: use recorded decisions/accounting, never infer a fill."""
    parts = [explain_decisions(row.decisions)]
    if row.action == "BUY":
        parts.append(f"{_money(row.execution_qty)}단위 매수 @ {_money(row.execution_price)} {currency}. "
                     f"매수비용 {_money(row.buy_fee)} {currency}, 잔여현금 {_money(row.cash_after)} {currency}.")
    elif row.action == "SELL":
        parts.append(f"{_money(row.execution_qty)}단위 전량 매도 @ {_money(row.execution_price)} {currency}. "
                     f"당일 비용 {_money(row.total_cost)} {currency}, 순손익 {_money(row.net_profit)} {currency}.")
    parts.append(f"보유 {row.trading_holding_days}거래일 / {row.calendar_holding_days}일. "
                 f"총자산 {_money(row.portfolio_value)} {currency}, 누적 비용 {_money(row.cumulative_cost)} {currency}.")
    return " ".join(parts)

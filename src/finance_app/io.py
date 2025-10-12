"""Utility helpers for loading finance data into the service layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping

from .models import Account, BudgetCategory, Transaction
from .services import FinanceService

_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y")


def parse_date(value: str | None) -> datetime | None:
    """Parse a date string using a selection of common formats.

    Parameters
    ----------
    value:
        String representation of a date or ``None``.

    Returns
    -------
    datetime | None
        ``datetime`` instance representing the provided date or ``None`` when
        no value was supplied.

    Raises
    ------
    ValueError
        If the string does not match any of the supported formats.
    """

    if value is None:
        return None

    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return parsed
    raise ValueError(f"Unsupported date format: {value!r}")


def load_accounts(data: Iterable[Mapping[str, Any]]) -> List[Account]:
    """Create :class:`Account` objects from serialised dictionaries."""

    return [
        Account(
            id=item["id"],
            name=item.get("name", item["id"]),
            initial_balance=float(item.get("initial_balance", 0.0)),
            currency=item.get("currency", "USD"),
        )
        for item in data
    ]


def load_budgets(data: Iterable[Mapping[str, Any]]) -> List[BudgetCategory]:
    """Create :class:`BudgetCategory` objects from serialised dictionaries."""

    return [
        BudgetCategory(
            name=item["name"],
            limit=float(item["limit"]) if item.get("limit") is not None else None,
            description=item.get("description", ""),
            tags=list(item.get("tags", [])),
        )
        for item in data
    ]


def load_transactions(data: Iterable[Mapping[str, Any]]) -> List[Transaction]:
    """Create :class:`Transaction` objects from serialised dictionaries."""

    transactions: List[Transaction] = []
    for item in data:
        date_value = item.get("date")
        transactions.append(
            Transaction(
                id=item["id"],
                account_id=item["account_id"],
                amount=float(item["amount"]),
                category=item.get("category"),
                description=item.get("description", ""),
                date=parse_date(date_value).date() if date_value else None,
            )
        )
    return transactions


def configure_service(service: FinanceService, payload: Mapping[str, Any]) -> FinanceService:
    """Populate ``service`` with entities described by ``payload``."""

    for account in load_accounts(payload.get("accounts", [])):
        service.add_account(account)

    for budget in load_budgets(payload.get("budgets", [])):
        service.add_budget_category(budget)

    for transaction in load_transactions(payload.get("transactions", [])):
        service.record_transaction(transaction)

    return service


def service_from_payload(payload: Mapping[str, Any]) -> FinanceService:
    """Construct a :class:`FinanceService` instance seeded with ``payload``."""

    return configure_service(FinanceService(), payload)


def demo_payload() -> Dict[str, Any]:
    """Return the sample dataset used across the project."""

    return {
        "accounts": [
            {"id": "checking", "name": "Everyday Checking", "initial_balance": 1500},
            {"id": "savings", "name": "Emergency Savings", "initial_balance": 4000},
        ],
        "budgets": [
            {"name": "groceries", "limit": 500},
            {"name": "entertainment", "limit": 200},
        ],
        "transactions": [
            {
                "id": "tx-001",
                "account_id": "checking",
                "amount": -125.45,
                "category": "groceries",
                "description": "Weekly supermarket run",
                "date": "2024-01-08",
            },
            {
                "id": "tx-002",
                "account_id": "checking",
                "amount": -48.20,
                "category": "entertainment",
                "description": "Cinema night",
                "date": "2024-01-12",
            },
            {
                "id": "tx-003",
                "account_id": "checking",
                "amount": 2500.00,
                "description": "Monthly salary",
                "date": "2024-01-15",
            },
            {
                "id": "tx-004",
                "account_id": "savings",
                "amount": 100.00,
                "description": "Interest payment",
                "date": "2024-01-31",
            },
        ],
    }


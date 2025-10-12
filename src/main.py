"""Command line entry point for the finance application."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from finance_app import Account, BudgetCategory, FinanceService, Transaction


def _parse_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value!r}")


def _load_accounts(data: Iterable[Dict[str, Any]]) -> List[Account]:
    return [
        Account(
            id=item["id"],
            name=item.get("name", item["id"]),
            initial_balance=float(item.get("initial_balance", 0.0)),
            currency=item.get("currency", "USD"),
        )
        for item in data
    ]


def _load_budgets(data: Iterable[Dict[str, Any]]) -> List[BudgetCategory]:
    return [
        BudgetCategory(
            name=item["name"],
            limit=float(item["limit"]) if item.get("limit") is not None else None,
            description=item.get("description", ""),
            tags=list(item.get("tags", [])),
        )
        for item in data
    ]


def _load_transactions(data: Iterable[Dict[str, Any]]) -> List[Transaction]:
    transactions: List[Transaction] = []
    for item in data:
        transactions.append(
            Transaction(
                id=item["id"],
                account_id=item["account_id"],
                amount=float(item["amount"]),
                category=item.get("category"),
                description=item.get("description", ""),
                date=_parse_date(item.get("date")) if item.get("date") else None,
            )
        )
    return transactions


def _configure_service(service: FinanceService, payload: Dict[str, Any]) -> FinanceService:
    for account in _load_accounts(payload.get("accounts", [])):
        service.add_account(account)

    for budget in _load_budgets(payload.get("budgets", [])):
        service.add_budget_category(budget)

    for transaction in _load_transactions(payload.get("transactions", [])):
        service.record_transaction(transaction)
    return service


def run_from_json(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    service = _configure_service(FinanceService(), payload)
    _print_summary(service)


def run_demo() -> None:
    payload = {
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

    service = _configure_service(FinanceService(), payload)
    _print_summary(service)


def _print_summary(service: FinanceService) -> None:
    print("Accounts and balances:")
    for account in service.accounts():
        balance = service.compute_balance(account.id)
        print(f"  - {account.name} ({account.id}): {balance:.2f} {account.currency}")

    print("\nBudget utilisation:")
    for summary in service.budget_report():
        if summary.limit is None:
            print(f"  - {summary.name}: spent {summary.spent:.2f}")
            continue
        remaining = summary.remaining if summary.remaining is not None else 0.0
        status = "under" if remaining >= 0 else "over"
        print(
            "  - {name}: spent {spent:.2f} / {limit:.2f} ({status} budget by {delta:.2f})".format(
                name=summary.name,
                spent=summary.spent,
                limit=summary.limit,
                status=status,
                delta=abs(remaining),
            )
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Finance application command line interface",
    )
    parser.add_argument(
        "--data",
        type=Path,
        help="Path to a JSON document describing accounts, budgets, and transactions.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the application with built-in sample data.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.data:
        run_from_json(args.data)
    elif args.demo:
        run_demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

"""Command line entry point for the finance application."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from finance_app import FinanceService
from finance_app.io import configure_service, demo_payload, service_from_payload


def run_from_json(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    service = configure_service(FinanceService(), payload)
    _print_summary(service)


def run_demo() -> None:
    service = service_from_payload(demo_payload())
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

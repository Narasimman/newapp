"""Service layer orchestrating the finance domain models."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional

from .models import Account, BudgetCategory, Transaction


class AccountExistsError(ValueError):
    """Raised when attempting to create an account that already exists."""


class UnknownAccountError(LookupError):
    """Raised when referencing an account that has not been registered."""


class FinanceService:
    """Facade that manages accounts, transactions, and budget categories."""

    def __init__(self) -> None:
        self._accounts: Dict[str, Account] = {}
        self._transactions: List[Transaction] = []
        self._budgets: Dict[str, BudgetCategory] = {}

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------
    def add_account(self, account: Account) -> None:
        """Register a new account with the service.

        Parameters
        ----------
        account:
            The account instance to add.

        Raises
        ------
        AccountExistsError
            If an account with the same ``id`` has already been registered.
        """

        if account.id in self._accounts:
            raise AccountExistsError(
                f"Account with id '{account.id}' already exists."
            )
        self._accounts[account.id] = account

    def get_account(self, account_id: str) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError as exc:
            raise UnknownAccountError(account_id) from exc

    def accounts(self) -> Iterator[Account]:
        return iter(self._accounts.values())

    # ------------------------------------------------------------------
    # Budget management
    # ------------------------------------------------------------------
    def add_budget_category(self, category: BudgetCategory) -> None:
        self._budgets[category.name] = category

    def get_budget_category(self, name: str) -> Optional[BudgetCategory]:
        return self._budgets.get(name)

    def budget_categories(self) -> Iterator[BudgetCategory]:
        return iter(self._budgets.values())

    # ------------------------------------------------------------------
    # Transaction management
    # ------------------------------------------------------------------
    def record_transaction(self, transaction: Transaction) -> None:
        """Persist a transaction in the ledger.

        The transaction is appended to the internal ledger. Accounts must be
        registered before transactions can be recorded.
        """

        if transaction.account_id not in self._accounts:
            raise UnknownAccountError(transaction.account_id)
        self._transactions.append(transaction)

    def transactions(self, account_id: Optional[str] = None) -> Iterator[Transaction]:
        """Iterate through transactions, optionally limited to an account."""

        for transaction in self._transactions:
            if account_id is None or transaction.account_id == account_id:
                yield transaction

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------
    def compute_balance(self, account_id: str) -> float:
        """Compute the balance for a single account."""

        account = self.get_account(account_id)
        running_total = account.initial_balance
        for transaction in self.transactions(account_id):
            running_total += transaction.amount
        return running_total

    def compute_balances(self) -> Dict[str, float]:
        """Compute balances for all registered accounts."""

        return {account.id: self.compute_balance(account.id) for account in self.accounts()}

    def aggregate_budget_spending(self) -> Dict[str, float]:
        """Aggregate spending for transactions assigned to budget categories.

        The service treats outflows (negative amounts) as expenses. Income
        transactions (positive amounts) do not contribute to the spending
        total, which keeps budget tracking focused on expenses.
        """

        totals: Dict[str, float] = defaultdict(float)
        for transaction in self._transactions:
            if transaction.category is None:
                continue
            if transaction.amount < 0:
                totals[transaction.category] += -transaction.amount
        return dict(totals)

    def budget_report(self) -> List["BudgetSummary"]:
        """Build a report summarising spending versus limits."""

        totals = self.aggregate_budget_spending()
        report: List[BudgetSummary] = []
        for name, category in self._budgets.items():
            spent = totals.get(name, 0.0)
            limit = category.limit
            remaining = None if limit is None else limit - spent
            report.append(
                BudgetSummary(
                    name=name,
                    limit=limit,
                    spent=spent,
                    remaining=remaining,
                )
            )
        return report


@dataclass(slots=True)
class BudgetSummary:
    """Container summarising spending against a budget limit."""

    name: str
    limit: Optional[float]
    spent: float
    remaining: Optional[float]

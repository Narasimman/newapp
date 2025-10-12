"""Domain models for the finance application."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(slots=True)
class Account:
    """Represents a financial account such as a bank or credit account.

    Attributes
    ----------
    id:
        Unique identifier for the account. This value is used when
        recording transactions and retrieving balances.
    name:
        Human friendly name of the account.
    initial_balance:
        Opening balance for the account. Transactions recorded through the
        application are applied on top of this amount when computing the
        current balance.
    currency:
        ISO 4217 currency code. The service does not perform currency
        conversions but the attribute is useful for display purposes.
    """

    id: str
    name: str
    initial_balance: float = 0.0
    currency: str = "USD"


@dataclass(slots=True)
class Transaction:
    """Represents a money movement affecting an account."""

    id: str
    account_id: str
    amount: float
    category: Optional[str] = None
    description: str = ""
    date: Optional[date] = None


@dataclass(slots=True)
class BudgetCategory:
    """Represents a tracked budget category.

    The ``limit`` attribute is optional. When it is ``None`` the budget is
    treated as informative tracking instead of an enforced spending limit.
    """

    name: str
    limit: Optional[float] = None
    description: str = ""
    tags: list[str] = field(default_factory=list)

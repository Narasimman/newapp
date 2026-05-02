"""Plaid API client wrapper."""

from __future__ import annotations

from datetime import date

import plaid
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest


class PlaidError(Exception):
    pass


class PlaidClient:
    _ENV_MAP = {
        "sandbox": plaid.Environment.Sandbox,
        "production": plaid.Environment.Production,
    }

    def __init__(self, client_id: str, secret: str, env: str = "sandbox") -> None:
        configuration = plaid.Configuration(
            host=self._ENV_MAP.get(env, plaid.Environment.Sandbox),
            api_key={"clientId": client_id, "secret": secret},
        )
        self._client = plaid_api.PlaidApi(plaid.ApiClient(configuration))

    def create_link_token(self, user_id: str = "default-user") -> str:
        try:
            req = LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(client_user_id=user_id),
                client_name="Personal Finance Tracker",
                products=[Products("transactions")],
                country_codes=[CountryCode("US")],
                language="en",
            )
            return self._client.link_token_create(req)["link_token"]
        except ApiException as exc:
            raise PlaidError(f"Failed to create link token: {exc.body}") from exc

    def exchange_public_token(self, public_token: str) -> tuple[str, str]:
        try:
            req = ItemPublicTokenExchangeRequest(public_token=public_token)
            resp = self._client.item_public_token_exchange(req)
            return resp["access_token"], resp["item_id"]
        except ApiException as exc:
            raise PlaidError(f"Failed to exchange token: {exc.body}") from exc

    def get_accounts(self, access_token: str) -> list[dict]:
        try:
            req = AccountsGetRequest(access_token=access_token)
            resp = self._client.accounts_get(req)
            result = []
            for acc in resp["accounts"]:
                acc_type = acc.type
                acc_subtype = acc.subtype
                result.append(
                    {
                        "account_id": acc.account_id,
                        "name": acc.name,
                        "official_name": acc.official_name,
                        "type": acc_type.value if hasattr(acc_type, "value") else str(acc_type),
                        "subtype": (
                            acc_subtype.value
                            if acc_subtype and hasattr(acc_subtype, "value")
                            else (str(acc_subtype) if acc_subtype else None)
                        ),
                        "balances": {
                            "current": acc.balances.current,
                            "available": acc.balances.available,
                            "iso_currency_code": acc.balances.iso_currency_code or "USD",
                        },
                    }
                )
            return result
        except ApiException as exc:
            raise PlaidError(f"Failed to get accounts: {exc.body}") from exc

    def sync_transactions(
        self, access_token: str, cursor: str | None = None
    ) -> tuple[list[dict], list[dict], list[str], str]:
        added: list[dict] = []
        modified: list[dict] = []
        removed: list[str] = []
        has_more = True
        next_cursor = cursor

        try:
            while has_more:
                req_kwargs: dict = {"access_token": access_token}
                if next_cursor:
                    req_kwargs["cursor"] = next_cursor
                resp = self._client.transactions_sync(TransactionsSyncRequest(**req_kwargs))

                for txn in resp["added"]:
                    added.append(self._parse_transaction(txn))
                for txn in resp["modified"]:
                    modified.append(self._parse_transaction(txn))
                for txn in resp["removed"]:
                    removed.append(txn.transaction_id)

                next_cursor = resp["next_cursor"]
                has_more = resp["has_more"]
        except ApiException as exc:
            raise PlaidError(f"Failed to sync transactions: {exc.body}") from exc

        return added, modified, removed, next_cursor

    def _parse_transaction(self, txn) -> dict:
        category = None
        pfc = getattr(txn, "personal_finance_category", None)
        if pfc:
            primary = getattr(pfc, "primary", None) or (
                pfc.get("primary") if isinstance(pfc, dict) else None
            )
            if primary:
                category = str(primary).replace("_", " ").title()
        if not category:
            cats = getattr(txn, "category", None)
            if cats:
                category = cats[0]

        txn_date = getattr(txn, "date", None)
        if isinstance(txn_date, str):
            txn_date = date.fromisoformat(txn_date)

        return {
            "transaction_id": txn.transaction_id,
            "account_id": txn.account_id,
            "amount": float(txn.amount),
            "date": txn_date,
            "name": txn.name or "",
            "merchant_name": getattr(txn, "merchant_name", None),
            "category": category,
            "pending": bool(txn.pending),
        }

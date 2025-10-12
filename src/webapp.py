"""Flask application providing a simple front-end for the finance service."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from typing import Any, Dict, Iterable, List
from uuid import uuid4

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from finance_app import Account, BudgetCategory, FinanceService, Transaction
from finance_app.io import demo_payload, parse_date, service_from_payload
from finance_app.services import AccountExistsError, UnknownAccountError


def create_app() -> Flask:
    """Application factory used by ``flask run``."""

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.setdefault("SECRET_KEY", "dev-finance-dashboard")
    app.config["FINANCE_SERVICE"] = service_from_payload(demo_payload())

    # ------------------------------------------------------------------
    # Template filters
    # ------------------------------------------------------------------
    @app.template_filter("format_currency")
    def format_currency(value: float | None) -> str:
        if value is None:
            return "—"
        return f"{value:,.2f}"

    @app.template_filter("format_date")
    def format_date(value: datetime | date | None) -> str:
        if value is None:
            return "—"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        return value.isoformat()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_service() -> FinanceService:
        return app.config["FINANCE_SERVICE"]

    def _set_service(service: FinanceService) -> None:
        app.config["FINANCE_SERVICE"] = service

    def _serialise_transactions(transactions: Iterable[Transaction]) -> List[Dict[str, Any]]:
        serialised: List[Dict[str, Any]] = []
        for txn in transactions:
            payload = asdict(txn)
            if isinstance(txn.date, datetime):
                payload["date"] = txn.date.date().isoformat()
            elif isinstance(txn.date, date):
                payload["date"] = txn.date.isoformat()
            else:
                payload["date"] = None
            serialised.append(payload)
        return serialised

    def _sorted_transactions(transactions: Iterable[Transaction]) -> List[Transaction]:
        return sorted(
            transactions,
            key=lambda txn: _transaction_timestamp(txn.date),
            reverse=True,
        )

    def _transaction_timestamp(value: datetime | date | None) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        return datetime.min

    def _build_account_rows(service: FinanceService) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for account in service.accounts():
            transactions = _sorted_transactions(service.transactions(account.id))
            rows.append(
                {
                    "account": account,
                    "balance": service.compute_balance(account.id),
                    "transactions": transactions,
                }
            )
        return rows

    def _build_budget_rows(service: FinanceService) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for summary in service.budget_report():
            limit = summary.limit
            spent = summary.spent
            percent = None
            if limit is not None and limit > 0:
                percent = min(100.0, max(0.0, (spent / limit) * 100))
            rows.append(
                {
                    "summary": summary,
                    "percent": percent,
                    "is_over": summary.remaining is not None and summary.remaining < 0,
                    "is_near_limit": percent is not None and not (summary.remaining is not None and summary.remaining < 0) and percent >= 80,
                }
            )
        return rows

    def _parse_tags(raw: str | None) -> List[str]:
        if not raw:
            return []
        return [tag.strip() for tag in raw.split(",") if tag.strip()]

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @app.get("/")
    def dashboard() -> str:
        service = _get_service()
        account_rows = _build_account_rows(service)
        budgets = _build_budget_rows(service)
        latest_transactions = _sorted_transactions(service.transactions())[:10]
        total_balance = sum(row["balance"] for row in account_rows)
        currency = account_rows[0]["account"].currency if account_rows else "USD"

        return render_template(
            "dashboard.html",
            accounts=account_rows,
            budgets=budgets,
            latest_transactions=latest_transactions,
            total_balance=total_balance,
            default_currency=currency,
        )

    @app.post("/accounts")
    def create_account() -> Response:
        service = _get_service()
        form = request.form
        account_id = form.get("id", "").strip()
        if not account_id:
            flash("Account ID is required.", "danger")
            return redirect(url_for("dashboard"))

        name = form.get("name", "").strip() or account_id
        try:
            initial_balance = float(form.get("initial_balance", 0) or 0)
        except ValueError:
            flash("Initial balance must be a number.", "danger")
            return redirect(url_for("dashboard"))

        currency = form.get("currency", "USD").strip().upper() or "USD"

        try:
            service.add_account(
                Account(
                    id=account_id,
                    name=name,
                    initial_balance=initial_balance,
                    currency=currency,
                )
            )
        except AccountExistsError:
            flash(f"Account with id '{account_id}' already exists.", "danger")
        else:
            flash(f"Account '{name}' created successfully.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/transactions")
    def create_transaction() -> Response:
        service = _get_service()
        form = request.form

        account_id = form.get("account_id", "").strip()
        if not account_id:
            flash("Please select an account for the transaction.", "danger")
            return redirect(url_for("dashboard"))

        transaction_id = form.get("id", "").strip() or f"tx-{uuid4().hex[:8]}"

        try:
            amount = float(form.get("amount", 0))
        except ValueError:
            flash("Transaction amount must be numeric.", "danger")
            return redirect(url_for("dashboard"))

        description = form.get("description", "").strip()
        category = form.get("category", "").strip() or None
        date_value = form.get("date", "").strip() or None

        try:
            parsed_date = parse_date(date_value).date() if date_value else None
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("dashboard"))

        transaction = Transaction(
            id=transaction_id,
            account_id=account_id,
            amount=amount,
            description=description,
            category=category,
            date=parsed_date,
        )

        try:
            service.record_transaction(transaction)
        except UnknownAccountError:
            flash("The selected account does not exist.", "danger")
        else:
            flash("Transaction recorded.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/budgets")
    def create_budget() -> Response:
        service = _get_service()
        form = request.form

        name = form.get("name", "").strip()
        if not name:
            flash("Budget name is required.", "danger")
            return redirect(url_for("dashboard"))

        limit_raw = form.get("limit", "").strip()
        try:
            limit = float(limit_raw) if limit_raw else None
        except ValueError:
            flash("Budget limit must be numeric.", "danger")
            return redirect(url_for("dashboard"))

        description = form.get("description", "").strip()
        tags = _parse_tags(form.get("tags"))

        service.add_budget_category(
            BudgetCategory(name=name, limit=limit, description=description, tags=tags)
        )
        flash("Budget saved.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/load-json")
    def load_json() -> Response:
        file = request.files.get("data_file")
        text = request.form.get("data_text", "").strip()

        payload: Dict[str, Any] | None = None
        if file and file.filename:
            try:
                payload = json.load(file)
            except json.JSONDecodeError:
                flash("Uploaded file is not valid JSON.", "danger")
                return redirect(url_for("dashboard"))
        elif text:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                flash("Provided JSON text is invalid.", "danger")
                return redirect(url_for("dashboard"))
        else:
            flash("Please select a file or paste JSON data.", "warning")
            return redirect(url_for("dashboard"))

        try:
            service = service_from_payload(payload)
        except (KeyError, TypeError, ValueError) as exc:
            flash(f"Unable to load data: {exc}", "danger")
            return redirect(url_for("dashboard"))

        _set_service(service)
        flash("Finance data loaded successfully.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/reset-demo")
    def reset_demo() -> Response:
        _set_service(service_from_payload(demo_payload()))
        flash("Demo dataset restored.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/export")
    def export_data() -> Response:
        service = _get_service()
        payload = {
            "accounts": [asdict(account) for account in service.accounts()],
            "budgets": [asdict(budget) for budget in service.budget_categories()],
            "transactions": _serialise_transactions(service.transactions()),
        }
        return app.response_class(
            json.dumps(payload, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=finance-data.json"},
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)


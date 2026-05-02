"""Flask application for the Plaid-integrated personal finance tracker."""

from __future__ import annotations

import os
from datetime import date, timedelta

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from sqlalchemy import func

from database import BankAccount, BankTransaction, PlaidItem, db
from plaid_client import PlaidClient, PlaidError

load_dotenv()


def _sync_item(item: PlaidItem, plaid_client: PlaidClient) -> int:
    added_txns, modified_txns, removed_ids, next_cursor = plaid_client.sync_transactions(
        item.access_token, item.cursor
    )

    for txn in added_txns:
        account = BankAccount.query.filter_by(plaid_account_id=txn["account_id"]).first()
        if not account:
            continue
        if BankTransaction.query.filter_by(plaid_transaction_id=txn["transaction_id"]).first():
            continue
        db.session.add(
            BankTransaction(
                plaid_transaction_id=txn["transaction_id"],
                account_id=account.id,
                amount=txn["amount"],
                date=txn["date"],
                name=txn["name"],
                merchant_name=txn["merchant_name"],
                category=txn["category"],
                pending=txn["pending"],
            )
        )

    for txn in modified_txns:
        existing = BankTransaction.query.filter_by(
            plaid_transaction_id=txn["transaction_id"]
        ).first()
        if existing:
            existing.amount = txn["amount"]
            existing.name = txn["name"]
            existing.merchant_name = txn["merchant_name"]
            existing.category = txn["category"]
            existing.pending = txn["pending"]

    for txn_id in removed_ids:
        existing = BankTransaction.query.filter_by(plaid_transaction_id=txn_id).first()
        if existing:
            db.session.delete(existing)

    item.cursor = next_cursor

    for acc_data in plaid_client.get_accounts(item.access_token):
        acc = BankAccount.query.filter_by(plaid_account_id=acc_data["account_id"]).first()
        if acc:
            acc.current_balance = acc_data["balances"]["current"]
            acc.available_balance = acc_data["balances"]["available"]

    db.session.commit()
    return len(added_txns)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///finance.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    plaid_client_id = os.environ.get("PLAID_CLIENT_ID")
    plaid_secret = os.environ.get("PLAID_SECRET")
    plaid_env = os.environ.get("PLAID_ENV", "sandbox")
    plaid = (
        PlaidClient(plaid_client_id, plaid_secret, plaid_env)
        if plaid_client_id and plaid_secret
        else None
    )

    # ------------------------------------------------------------------ #
    # Pages                                                                #
    # ------------------------------------------------------------------ #

    @app.get("/")
    def index():
        accounts = BankAccount.query.all()
        return render_template(
            "dashboard.html",
            accounts=accounts,
            plaid_configured=plaid is not None,
        )

    # ------------------------------------------------------------------ #
    # Plaid Link                                                           #
    # ------------------------------------------------------------------ #

    @app.post("/api/create-link-token")
    def create_link_token():
        if not plaid:
            return jsonify({"error": "Plaid not configured"}), 503
        try:
            return jsonify({"link_token": plaid.create_link_token()})
        except PlaidError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/exchange-token")
    def exchange_token():
        if not plaid:
            return jsonify({"error": "Plaid not configured"}), 503

        data = request.get_json(force=True)
        public_token = data.get("public_token")
        metadata = data.get("metadata", {})
        if not public_token:
            return jsonify({"error": "Missing public_token"}), 400

        try:
            access_token, item_id = plaid.exchange_public_token(public_token)
        except PlaidError as exc:
            return jsonify({"error": str(exc)}), 400

        if PlaidItem.query.filter_by(item_id=item_id).first():
            return jsonify({"error": "Account already connected"}), 409

        institution = metadata.get("institution", {})
        item = PlaidItem(
            item_id=item_id,
            access_token=access_token,
            institution_name=institution.get("name", "Unknown Bank"),
            institution_id=institution.get("institution_id"),
        )
        db.session.add(item)
        db.session.flush()

        for acc_data in plaid.get_accounts(access_token):
            db.session.add(
                BankAccount(
                    plaid_account_id=acc_data["account_id"],
                    item_id=item.id,
                    name=acc_data["name"],
                    official_name=acc_data["official_name"],
                    account_type=acc_data["type"],
                    subtype=acc_data["subtype"],
                    current_balance=acc_data["balances"]["current"],
                    available_balance=acc_data["balances"]["available"],
                    currency=acc_data["balances"]["iso_currency_code"],
                )
            )

        db.session.commit()

        try:
            added = _sync_item(item, plaid)
        except PlaidError:
            added = 0

        return jsonify(
            {
                "status": "ok",
                "institution": item.institution_name,
                "transactions_added": added,
            }
        )

    # ------------------------------------------------------------------ #
    # Sync                                                                 #
    # ------------------------------------------------------------------ #

    @app.post("/api/sync")
    def sync_all():
        if not plaid:
            return jsonify({"error": "Plaid not configured"}), 503

        total_added = 0
        errors = []
        for item in PlaidItem.query.all():
            try:
                total_added += _sync_item(item, plaid)
            except PlaidError as exc:
                errors.append({"institution": item.institution_name, "error": str(exc)})

        return jsonify({"status": "ok", "added": total_added, "errors": errors})

    # ------------------------------------------------------------------ #
    # Data endpoints                                                       #
    # ------------------------------------------------------------------ #

    @app.get("/api/accounts")
    def get_accounts():
        accounts = BankAccount.query.all()
        return jsonify(
            [
                {
                    "id": a.id,
                    "name": a.name,
                    "official_name": a.official_name,
                    "type": a.account_type,
                    "subtype": a.subtype,
                    "current_balance": a.current_balance,
                    "available_balance": a.available_balance,
                    "currency": a.currency,
                    "institution": a.item.institution_name,
                    "item_id": a.item.id,
                }
                for a in accounts
            ]
        )

    @app.get("/api/transactions")
    def get_transactions():
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        account_id = request.args.get("account_id", type=int)
        days = request.args.get("days", type=int)

        query = BankTransaction.query
        if account_id:
            query = query.filter_by(account_id=account_id)
        if days:
            cutoff = date.today() - timedelta(days=days)
            query = query.filter(BankTransaction.date >= cutoff)

        total = query.count()
        txns = (
            query.order_by(BankTransaction.date.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return jsonify(
            {
                "total": total,
                "transactions": [
                    {
                        "id": t.id,
                        "date": t.date.isoformat(),
                        "name": t.name,
                        "merchant_name": t.merchant_name,
                        "amount": t.amount,
                        "category": t.category,
                        "pending": t.pending,
                        "account_id": t.account_id,
                        "account_name": t.account.name,
                    }
                    for t in txns
                ],
            }
        )

    @app.get("/api/spending-summary")
    def spending_summary():
        days = request.args.get("days", 30, type=int)
        cutoff = date.today() - timedelta(days=days)

        category_rows = (
            db.session.query(
                BankTransaction.category,
                func.sum(BankTransaction.amount).label("total"),
            )
            .filter(
                BankTransaction.date >= cutoff,
                BankTransaction.amount > 0,
                BankTransaction.pending == False,  # noqa: E712
            )
            .group_by(BankTransaction.category)
            .order_by(func.sum(BankTransaction.amount).desc())
            .all()
        )

        monthly_rows = (
            db.session.query(
                func.strftime("%Y-%m", BankTransaction.date).label("month"),
                func.sum(BankTransaction.amount).label("total"),
            )
            .filter(
                BankTransaction.amount > 0,
                BankTransaction.pending == False,  # noqa: E712
            )
            .group_by("month")
            .order_by("month")
            .limit(12)
            .all()
        )

        return jsonify(
            {
                "categories": [
                    {"category": c or "Uncategorized", "total": round(float(t), 2)}
                    for c, t in category_rows
                ],
                "monthly": [
                    {"month": m, "total": round(float(t), 2)} for m, t in monthly_rows
                ],
            }
        )

    @app.delete("/api/items/<int:item_id>")
    def remove_item(item_id: int):
        item = db.get_or_404(PlaidItem, item_id)
        db.session.delete(item)
        db.session.commit()
        return jsonify({"status": "ok"})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

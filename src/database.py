"""SQLAlchemy models for the finance tracker."""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class PlaidItem(db.Model):
    __tablename__ = "plaid_items"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.String(255), unique=True, nullable=False)
    access_token = db.Column(db.String(255), nullable=False)
    institution_id = db.Column(db.String(100))
    institution_name = db.Column(db.String(255))
    cursor = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    accounts = db.relationship(
        "BankAccount", backref="item", lazy=True, cascade="all, delete-orphan"
    )


class BankAccount(db.Model):
    __tablename__ = "bank_accounts"

    id = db.Column(db.Integer, primary_key=True)
    plaid_account_id = db.Column(db.String(255), unique=True, nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("plaid_items.id"), nullable=False)
    name = db.Column(db.String(255))
    official_name = db.Column(db.String(255))
    account_type = db.Column(db.String(50))
    subtype = db.Column(db.String(50))
    current_balance = db.Column(db.Float)
    available_balance = db.Column(db.Float)
    currency = db.Column(db.String(10), default="USD")

    transactions = db.relationship(
        "BankTransaction", backref="account", lazy=True, cascade="all, delete-orphan"
    )


class BankTransaction(db.Model):
    __tablename__ = "bank_transactions"

    id = db.Column(db.Integer, primary_key=True)
    plaid_transaction_id = db.Column(db.String(255), unique=True, nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(255))
    merchant_name = db.Column(db.String(255))
    category = db.Column(db.String(255))
    pending = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

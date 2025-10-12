# Finance Application Prototype

This project provides a lightweight finance application skeleton featuring
basic domain models, a service layer to coordinate operations, and a command
line entry point to explore the behaviour. The code is organised under the
`src/` directory using a standard package layout.

## Project structure

```
src/
├── finance_app/
│   ├── __init__.py          # Package initialiser exposing public API
│   ├── models.py            # Dataclasses for accounts, transactions, budgets
│   └── services.py          # FinanceService orchestrating the domain
└── main.py                  # CLI entry point wiring services together
```

## Features

* Register accounts with an opening balance and currency metadata.
* Record transactions and obtain per-account running balances.
* Track budget categories and aggregate expense totals per category.
* Generate a human readable budget report highlighting how much is left for
  each tracked category.

## Getting started

The project targets Python 3.11+. The command line interface only depends on
the Python standard library—set the ``PYTHONPATH`` and run it in one of the
following modes.

### Run the demo scenario

```
PYTHONPATH=src python -m main --demo
```

The command seeds the in-memory service with example accounts, budgets, and
transactions before printing a balance and budget summary.

### Load data from JSON

Provide a JSON document describing the financial entities. The file must use
an object with three optional arrays: ``accounts``, ``budgets`` and
``transactions``. A minimal example:

```json
{
  "accounts": [
    {"id": "checking", "name": "Household Checking", "initial_balance": 950}
  ],
  "budgets": [
    {"name": "groceries", "limit": 400}
  ],
  "transactions": [
    {
      "id": "tx-1",
      "account_id": "checking",
      "amount": -120.45,
      "category": "groceries",
      "description": "Weekly shop",
      "date": "2024-02-01"
    }
  ]
}
```

Run the CLI pointing to the document:

```
PYTHONPATH=src python -m main --data path/to/finance-data.json
```

Accounts, budgets, and transactions are created in memory for the duration of
that command and a summary is printed to standard output.

## Web dashboard

A lightweight Flask front end is available for exploring the service in the
browser. It displays account balances, recent transactions, and budget
utilisation while also providing forms to add new entries or load data from a
JSON document.

```bash
pip install -r requirements.txt
FLASK_APP=webapp:create_app FLASK_ENV=development flask run
```

The application starts with the same demo dataset used by the CLI. Use the
"Load demo data" button in the navigation bar to reset the state at any time or
upload your own JSON document from the dashboard.

## Extending the prototype

The current implementation keeps everything in memory, which makes it suitable
for experimentation or as a starting point for a fuller application. Possible
next steps include:

* Persisting the ledger to a database or file system storage.
* Adding authentication/authorisation around account access.
* Exposing the service layer via a REST API or web interface.
* Introducing richer reporting (cash flow trends, net worth analytics, etc.).

Contributions and ideas are welcome!

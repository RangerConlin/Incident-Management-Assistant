from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from utils import incident_storage

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MASTER_DB = DATA_DIR / "master.db"

MASTER_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS vendors (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        contacts_json TEXT,
        payment_terms TEXT,
        notes TEXT
    )
    """,
]

INCIDENT_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS finance_fuel_price_profiles (
        id INTEGER PRIMARY KEY,
        incident_id TEXT NOT NULL,
        operational_period_id TEXT,
        gasoline_price REAL NOT NULL,
        diesel_price REAL NOT NULL,
        jet_a_price REAL NOT NULL,
        aviation_100ll_price REAL NOT NULL,
        location_note TEXT,
        source_note TEXT,
        entered_by TEXT,
        entered_at DATETIME NOT NULL,
        effective_at DATETIME NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS finance_forecasts (
        id INTEGER PRIMARY KEY,
        incident_id TEXT NOT NULL,
        operational_period_id TEXT,
        forecast_name TEXT NOT NULL,
        forecast_type TEXT NOT NULL,
        category TEXT NOT NULL,
        status TEXT NOT NULL,
        total_estimated_cost REAL NOT NULL DEFAULT 0,
        total_estimated_gallons REAL NOT NULL DEFAULT 0,
        created_by TEXT,
        created_at DATETIME NOT NULL,
        submitted_at DATETIME,
        approved_by TEXT,
        approved_at DATETIME,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS finance_fuel_forecast_lines (
        id INTEGER PRIMARY KEY,
        forecast_id INTEGER NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id TEXT,
        resource_name TEXT NOT NULL,
        fuel_type TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        estimated_miles_per_resource REAL,
        estimated_total_miles REAL NOT NULL DEFAULT 0,
        estimated_mpg REAL,
        estimated_hours REAL,
        gallons_per_hour REAL,
        fuel_price REAL NOT NULL,
        estimated_gallons REAL NOT NULL,
        estimated_cost REAL NOT NULL,
        linked_task_id TEXT,
        notes TEXT,
        FOREIGN KEY (forecast_id) REFERENCES finance_forecasts(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS finance_funding_sources (
        id INTEGER PRIMARY KEY,
        incident_id TEXT NOT NULL,
        name TEXT NOT NULL,
        code TEXT,
        type TEXT NOT NULL,
        agency TEXT,
        starting_balance REAL,
        current_balance REAL,
        notes TEXT,
        is_active INTEGER NOT NULL DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS finance_expenses (
        id INTEGER PRIMARY KEY,
        incident_id TEXT NOT NULL,
        operational_period_id TEXT,
        expense_number TEXT NOT NULL,
        category TEXT NOT NULL,
        subcategory TEXT,
        description TEXT NOT NULL,
        vendor TEXT,
        expense_datetime DATETIME NOT NULL,
        amount_subtotal REAL NOT NULL,
        amount_tax REAL NOT NULL DEFAULT 0,
        amount_tip REAL NOT NULL DEFAULT 0,
        amount_total REAL NOT NULL,
        payment_method TEXT,
        funding_source_id INTEGER,
        status TEXT NOT NULL,
        entered_by TEXT,
        entered_at DATETIME NOT NULL,
        submitted_at DATETIME,
        approved_by TEXT,
        approved_at DATETIME,
        paid_at DATETIME,
        notes TEXT,
        linked_forecast_id INTEGER,
        receipt_attached INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS finance_expense_lines (
        id INTEGER PRIMARY KEY,
        expense_id INTEGER NOT NULL,
        item_description TEXT NOT NULL,
        quantity REAL,
        unit TEXT,
        unit_cost REAL,
        tax_amount REAL,
        line_total REAL NOT NULL,
        category TEXT,
        notes TEXT,
        FOREIGN KEY (expense_id) REFERENCES finance_expenses(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS finance_expense_links (
        id INTEGER PRIMARY KEY,
        expense_id INTEGER NOT NULL,
        linked_type TEXT NOT NULL,
        linked_id TEXT NOT NULL,
        relationship_type TEXT,
        notes TEXT,
        FOREIGN KEY (expense_id) REFERENCES finance_expenses(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS finance_approvals (
        id INTEGER PRIMARY KEY,
        incident_id TEXT NOT NULL,
        record_type TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        approver_id TEXT,
        approver_role TEXT,
        action TEXT NOT NULL,
        comments TEXT,
        timestamp DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS finance_attachments (
        id INTEGER PRIMARY KEY,
        incident_id TEXT NOT NULL,
        record_type TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT,
        attachment_type TEXT NOT NULL,
        uploaded_by TEXT,
        uploaded_at DATETIME NOT NULL,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS finance_audit_log (
        id INTEGER PRIMARY KEY,
        incident_id TEXT NOT NULL,
        record_type TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        timestamp DATETIME NOT NULL,
        changed_by TEXT,
        field_changed TEXT,
        old_value TEXT,
        new_value TEXT,
        change_reason TEXT
    )
    """,
]


def _init_db(engine: Engine, statements: list[str]) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        for stmt in statements:
            conn.exec_driver_sql(stmt)


def get_master_engine() -> Engine:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{MASTER_DB}")
    _init_db(engine, MASTER_TABLES)
    return engine


def get_incident_engine(incident_id: str) -> Engine:
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        metadata = incident_storage.infer_incident_metadata(str(incident_id))
        paths = incident_storage.get_incident_paths(
            incident_number=metadata.get("incident_number") or incident_id,
            incident_name=metadata.get("name") or incident_id,
            incident_id=metadata.get("incident_id") or incident_id,
        )
        incident_storage.ensure_incident_structure(paths, metadata)
    engine = create_engine(f"sqlite:///{paths.incident_db}")
    _init_db(engine, INCIDENT_TABLES)
    return engine


@contextmanager
def with_master_session() -> Generator[Session, None, None]:
    session = sessionmaker(bind=get_master_engine(), autocommit=False, autoflush=False)()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def with_incident_session(incident_id: str) -> Generator[Session, None, None]:
    session = sessionmaker(bind=get_incident_engine(incident_id), autocommit=False, autoflush=False)()
    try:
        yield session
    finally:
        session.close()

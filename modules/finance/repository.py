from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MASTER_DB = DATA_DIR / "master.db"
MISSIONS_DIR = DATA_DIR / "missions"

# -- table initialization ----------------------------------------------------

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
    """
    CREATE TABLE IF NOT EXISTS labor_rates (
        id INTEGER PRIMARY KEY,
        title TEXT,
        rate_per_hour REAL,
        overtime_mult REAL,
        effective_from DATE,
        effective_to DATE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS equipment_rates (
        id INTEGER PRIMARY KEY,
        type TEXT,
        rate_per_hour REAL,
        rate_per_day REAL,
        effective_from DATE,
        effective_to DATE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS approval_chains (
        id INTEGER PRIMARY KEY,
        name TEXT,
        steps_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY,
        code TEXT,
        name TEXT,
        category TEXT
    )
    """,
]

MISSION_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS time_entries (
        id INTEGER PRIMARY KEY,
        mission_id TEXT,
        person_id INTEGER,
        role TEXT,
        op_period TEXT,
        date DATE,
        hours_worked REAL,
        overtime_hours REAL,
        labor_rate_id INTEGER,
        equipment_id INTEGER,
        notes TEXT,
        status TEXT,
        approved_by INTEGER,
        approved_at DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS requisitions (
        id INTEGER PRIMARY KEY,
        mission_id TEXT,
        req_number TEXT,
        request_id INTEGER,
        requestor_id INTEGER,
        date DATE,
        description TEXT,
        amount_est REAL,
        status TEXT,
        approval_chain_id INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY,
        mission_id TEXT,
        po_number TEXT,
        vendor_id INTEGER,
        req_id INTEGER,
        date DATE,
        amount_auth REAL,
        status TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY,
        mission_id TEXT,
        po_id INTEGER,
        date DATE,
        qty REAL,
        amount REAL,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY,
        mission_id TEXT,
        po_id INTEGER,
        vendor_invoice_no TEXT,
        date DATE,
        amount REAL,
        status TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cost_entries (
        id INTEGER PRIMARY KEY,
        mission_id TEXT,
        date DATE,
        account_id INTEGER,
        description TEXT,
        amount REAL,
        source TEXT,
        ref_table TEXT,
        ref_id INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_cost_summary (
        id INTEGER PRIMARY KEY,
        mission_id TEXT,
        date DATE,
        total_labor REAL,
        total_equipment REAL,
        total_procurement REAL,
        total_other REAL,
        notes TEXT,
        finalized_by INTEGER,
        finalized_at DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY,
        mission_id TEXT,
        account_id INTEGER,
        amount_budgeted REAL,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claims (
        id INTEGER PRIMARY KEY,
        mission_id TEXT,
        claim_type TEXT,
        claimant_id INTEGER,
        date_reported DATE,
        description TEXT,
        amount_est REAL,
        status TEXT,
        attachments_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS approvals (
        id INTEGER PRIMARY KEY,
        mission_id TEXT,
        entity TEXT,
        entity_id INTEGER,
        step TEXT,
        actor_id INTEGER,
        action TEXT,
        timestamp DATETIME,
        comments TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS finance_audit (
        id INTEGER PRIMARY KEY,
        mission_id TEXT,
        entity TEXT,
        entity_id INTEGER,
        action TEXT,
        who INTEGER,
        when DATETIME,
        details_json TEXT
    )
    """,
]


def _init_db(engine: Engine, statements: list[str]) -> None:
    with engine.begin() as conn:
        for stmt in statements:
            conn.exec_driver_sql(stmt)


def get_master_engine() -> Engine:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{MASTER_DB}")
    _init_db(engine, MASTER_TABLES)
    return engine


def get_mission_engine(mission_id: str) -> Engine:
    mission_path = MISSIONS_DIR / f"{mission_id}.db"
    mission_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{mission_path}")
    _init_db(engine, MISSION_TABLES)
    return engine


@contextmanager
def with_master_session() -> Generator[Session, None, None]:
    engine = get_master_engine()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def with_mission_session(mission_id: str) -> Generator[Session, None, None]:
    engine = get_mission_engine(mission_id)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

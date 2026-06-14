"""pyodbc connection helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

import pyodbc

from app.config import get_connection_string


def connect(env: str) -> pyodbc.Connection:
    conn_str = get_connection_string(env)
    return pyodbc.connect(conn_str, autocommit=False)


@contextmanager
def connection(env: str) -> Generator[pyodbc.Connection, None, None]:
    conn = connect(env)
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(conn: pyodbc.Connection, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(sql, params or ())
    if cursor.description is None:
        return []
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_one(conn: pyodbc.Connection, sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
    rows = fetch_all(conn, sql, params)
    return rows[0] if rows else None


def execute(conn: pyodbc.Connection, sql: str, params: tuple[Any, ...] | None = None) -> None:
    cursor = conn.cursor()
    cursor.execute(sql, params or ())
    conn.commit()


def table_exists(conn: pyodbc.Connection, schema: str, table: str) -> bool:
    row = fetch_one(
        conn,
        """
        SELECT 1 AS found
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        """,
        (schema, table),
    )
    return row is not None

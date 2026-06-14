"""Copy rows from production to a target database."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

import pyodbc

from app.config import get_target_connections, is_valid_target
from app.database import connection
from app.schema import ensure_table_exists, get_column_definitions, get_primary_key_columns
from app.sql_parser import build_table_select, extract_table_refs, extract_top_limit, validate_select_only

ProgressCallback = Callable[[str, dict[str, Any] | None], None]


def _quote(name: str) -> str:
    return f"[{name.replace(']', ']]')}]"


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _serialize_value(val) for key, val in row.items()}


def _fetch_rows(conn: pyodbc.Connection, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
    cursor = conn.cursor()
    cursor.execute(sql)
    if cursor.description is None:
        return [], []
    columns = [col[0] for col in cursor.description]
    rows = [dict(zip(columns, record)) for record in cursor.fetchall()]
    return columns, rows


def _upsert_rows(
    target_conn: pyodbc.Connection,
    schema: str,
    table: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    key_columns: list[str],
) -> int:
    if not rows:
        return 0

    qualified = f"{_quote(schema)}.{_quote(table)}"

    col_defs = get_column_definitions(target_conn, schema, table)
    identity_cols = {col["COLUMN_NAME"] for col in col_defs if col.get("IS_IDENTITY")}
    preserve_identity = bool(identity_cols.intersection(key_columns or columns))
    insert_columns = columns if preserve_identity else [c for c in columns if c not in identity_cols]
    insert_col_list = ", ".join(_quote(c) for c in insert_columns)
    insert_placeholders = ", ".join("?" for _ in insert_columns)
    insert_sql = f"INSERT INTO {qualified} ({insert_col_list}) VALUES ({insert_placeholders})"

    cursor = target_conn.cursor()
    inserted = 0
    match_columns = key_columns if key_columns else columns

    if preserve_identity:
        cursor.execute(f"SET IDENTITY_INSERT {qualified} ON")

    for row in rows:
        if match_columns:
            match_clause = " AND ".join(
                f"(t.{_quote(c)} = ? OR (t.{_quote(c)} IS NULL AND ? IS NULL))"
                for c in match_columns
            )
            exists_params: list[Any] = []
            for col in match_columns:
                val = row.get(col)
                exists_params.extend([val, val])
            cursor.execute(f"SELECT 1 FROM {qualified} t WHERE {match_clause}", exists_params)
        else:
            cursor.execute(f"SELECT 1 FROM {qualified} t")
        if cursor.fetchone():
            continue
        cursor.execute(insert_sql, tuple(row[c] for c in insert_columns))
        inserted += 1

    if preserve_identity:
        cursor.execute(f"SET IDENTITY_INSERT {qualified} OFF")

    target_conn.commit()
    return inserted


def preview_query(sql: str, limit: int) -> dict[str, Any]:
    from app.sql_parser import wrap_preview_query

    preview_sql = wrap_preview_query(sql, limit)
    with connection("production") as conn:
        columns, rows = _fetch_rows(conn, preview_sql)
    return {
        "columns": columns,
        "rows": [_serialize_row(row) for row in rows],
        "sql": preview_sql,
    }


def sync_query(sql: str, target_env: str, emit: ProgressCallback) -> dict[str, Any]:
    validate_select_only(sql)

    if not is_valid_target(target_env):
        available = ", ".join(get_target_connections()) or "(none configured)"
        raise ValueError(f"Unknown target '{target_env}'. Available targets: {available}")

    table_refs = extract_table_refs(sql)
    if not table_refs:
        raise ValueError("No tables found in query")

    top_limit = extract_top_limit(sql)
    summary: dict[str, int] = {}
    total_rows = 0

    emit("Connecting to production...", None)
    emit(f"Connecting to {target_env}...", None)
    if top_limit is not None:
        emit(f"Query uses TOP ({top_limit}) — syncing at most {top_limit} row(s) per table.", None)

    with connection("production") as prod_conn, connection(target_env) as target_conn:
        for ref in table_refs:
            table_sql = build_table_select(sql, ref)
            qualified = ref.qualified_name

            emit(f"Fetching rows from {qualified}...", {"table": qualified})
            columns, rows = _fetch_rows(prod_conn, table_sql)
            emit(
                f"Fetching rows from {qualified} ({len(rows)} rows found)...",
                {"table": qualified, "count": len(rows)},
            )

            created = ensure_table_exists(prod_conn, target_conn, ref.schema, ref.table)
            if created:
                emit(
                    f"Creating table {qualified} in {target_env}...",
                    {"table": qualified, "created": True},
                )

            key_columns = get_primary_key_columns(prod_conn, ref.schema, ref.table)
            emit(f"Inserting rows into {qualified}...", {"table": qualified})

            copied = _upsert_rows(
                target_conn,
                ref.schema,
                ref.table,
                columns,
                rows,
                key_columns,
            )
            summary[qualified] = copied
            total_rows += copied
            emit(
                f"Inserted {copied} new row(s) into {qualified}.",
                {"table": qualified, "inserted": copied},
            )

    table_count = len(table_refs)
    emit(
        f"Done. {total_rows} rows copied across {table_count} table(s).",
        {"totalRows": total_rows, "tableCount": table_count, "summary": summary},
    )
    return {"totalRows": total_rows, "tableCount": table_count, "summary": summary}

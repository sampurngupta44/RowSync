"""Schema introspection and DDL generation."""

from __future__ import annotations

from typing import Any

import pyodbc

from app.database import fetch_all, table_exists


def load_schema(conn: pyodbc.Connection) -> dict[str, Any]:
    """Load tables, columns, and aliases for autocomplete."""
    tables = fetch_all(
        conn,
        """
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """,
    )
    columns = fetch_all(
        conn,
        """
        SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.COLUMNS
        ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
        """,
    )

    table_map: dict[str, dict[str, Any]] = {}
    for row in tables:
        key = f"{row['TABLE_SCHEMA']}.{row['TABLE_NAME']}"
        table_map[key] = {
            "schema": row["TABLE_SCHEMA"],
            "name": row["TABLE_NAME"],
            "columns": [],
        }

    for row in columns:
        key = f"{row['TABLE_SCHEMA']}.{row['TABLE_NAME']}"
        if key in table_map:
            table_map[key]["columns"].append(row["COLUMN_NAME"])

    table_list = sorted(table_map.keys())
    return {
        "tables": table_list,
        "tableDetails": table_map,
        "columnsByTable": {key: table_map[key]["columns"] for key in table_list},
    }


def get_primary_key_columns(conn: pyodbc.Connection, schema: str, table: str) -> list[str]:
    rows = fetch_all(
        conn,
        """
        SELECT k.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE k
          ON tc.CONSTRAINT_NAME = k.CONSTRAINT_NAME
         AND tc.TABLE_SCHEMA = k.TABLE_SCHEMA
         AND tc.TABLE_NAME = k.TABLE_NAME
        WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
          AND tc.TABLE_SCHEMA = ?
          AND tc.TABLE_NAME = ?
        ORDER BY k.ORDINAL_POSITION
        """,
        (schema, table),
    )
    return [row["COLUMN_NAME"] for row in rows]


def get_column_definitions(conn: pyodbc.Connection, schema: str, table: str) -> list[dict[str, Any]]:
    return fetch_all(
        conn,
        """
        SELECT
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.NUMERIC_PRECISION,
            c.NUMERIC_SCALE,
            c.IS_NULLABLE,
            c.COLUMN_DEFAULT,
            COLUMNPROPERTY(OBJECT_ID(c.TABLE_SCHEMA + '.' + c.TABLE_NAME), c.COLUMN_NAME, 'IsIdentity') AS IS_IDENTITY
        FROM INFORMATION_SCHEMA.COLUMNS c
        WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
        ORDER BY c.ORDINAL_POSITION
        """,
        (schema, table),
    )


def _format_data_type(col: dict[str, Any]) -> str:
    data_type = col["DATA_TYPE"].upper()
    length = col["CHARACTER_MAXIMUM_LENGTH"]
    precision = col["NUMERIC_PRECISION"]
    scale = col["NUMERIC_SCALE"]

    if data_type in {"CHAR", "NCHAR", "VARCHAR", "NVARCHAR", "BINARY", "VARBINARY"}:
        if length is None or length == -1:
            return f"{data_type}(MAX)"
        return f"{data_type}({length})"

    if data_type in {"DECIMAL", "NUMERIC"}:
        return f"{data_type}({precision},{scale})"

    if data_type in {"DATETIME2", "DATETIMEOFFSET", "TIME"} and scale is not None:
        return f"{data_type}({scale})"

    return data_type


def build_create_table_sql(conn: pyodbc.Connection, schema: str, table: str) -> str:
    columns = get_column_definitions(conn, schema, table)
    if not columns:
        raise ValueError(f"No columns found for {schema}.{table}")

    pk_cols = get_primary_key_columns(conn, schema, table)
    lines: list[str] = []

    for col in columns:
        line = f"    [{col['COLUMN_NAME']}] {_format_data_type(col)}"
        if col["IS_IDENTITY"]:
            line += " IDENTITY(1,1)"
        if col["IS_NULLABLE"] == "NO":
            line += " NOT NULL"
        lines.append(line)

    pk_clause = ""
    if pk_cols:
        pk_names = ", ".join(f"[{name}]" for name in pk_cols)
        pk_clause = f",\n    PRIMARY KEY ({pk_names})"

    return (
        f"CREATE TABLE [{schema}].[{table}] (\n"
        + ",\n".join(lines)
        + pk_clause
        + "\n)"
    )


def ensure_table_exists(
    prod_conn: pyodbc.Connection,
    target_conn: pyodbc.Connection,
    schema: str,
    table: str,
) -> bool:
    """Create table in target from production schema if missing. Returns True if created."""
    if table_exists(target_conn, schema, table):
        return False
    ddl = build_create_table_sql(prod_conn, schema, table)
    cursor = target_conn.cursor()
    cursor.execute(ddl)
    target_conn.commit()
    return True

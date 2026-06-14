"""Parse SQL SELECT queries and extract table references."""

from __future__ import annotations

import re
from dataclasses import dataclass

import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Token
from sqlparse.tokens import Keyword


@dataclass(frozen=True)
class TableRef:
    schema: str
    table: str
    alias: str

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.table}"

    @property
    def select_prefix(self) -> str:
        """Token used in SELECT DISTINCT prefix (alias or table name)."""
        return self.alias


TOP_PATTERN = re.compile(
    r"\bTOP\s+(?:\(\s*(\d+)\s*\)|(\d+))(?:\s+WITH\s+TIES)?",
    re.IGNORECASE,
)


def extract_top_limit(sql: str) -> int | None:
    """Return the row limit from TOP (N) / TOP N in the user's query."""
    if re.search(r"\bTOP\s+\(?\s*\d+\s*\)?\s+PERCENT\b", sql, re.IGNORECASE):
        return None
    match = TOP_PATTERN.search(sql)
    if not match:
        return None
    value = match.group(1) or match.group(2)
    return int(value) if value else None


def _strip_brackets(name: str) -> str:
    name = name.strip()
    if name.startswith("[") and name.endswith("]"):
        return name[1:-1]
    return name


def _parse_identifier(identifier: Identifier) -> tuple[str, str, str]:
    parent = identifier.get_parent_name()
    real_name = _strip_brackets(identifier.get_real_name() or identifier.value)
    alias_token = identifier.get_alias()
    alias = _strip_brackets(alias_token) if alias_token else real_name

    if parent:
        schema = _strip_brackets(parent)
        table = real_name
    else:
        parts = real_name.split(".")
        if len(parts) == 2:
            schema, table = _strip_brackets(parts[0]), _strip_brackets(parts[1])
        else:
            schema, table = "dbo", real_name

    return schema, table, alias


def _extract_tables_from_token(token: Token, tables: list[TableRef]) -> None:
    if isinstance(token, IdentifierList):
        for child in token.get_identifiers():
            _extract_tables_from_token(child, tables)
        return

    if isinstance(token, Identifier):
        schema, table, alias = _parse_identifier(token)
        tables.append(TableRef(schema=schema, table=table, alias=alias))
        return

    if token.is_group:
        for child in token.tokens:
            _extract_tables_from_token(child, tables)


def _find_from_index(tokens: list[Token]) -> int | None:
    paren_depth = 0
    for idx, token in enumerate(tokens):
        if token.ttype is sqlparse.tokens.Punctuation:
            if token.value == "(":
                paren_depth += 1
            elif token.value == ")":
                paren_depth = max(0, paren_depth - 1)
        if paren_depth == 0 and token.ttype is Keyword and token.normalized == "FROM":
            return idx
    return None


def _trim_trailing_query_clauses(from_sql: str) -> str:
    """Remove ORDER BY / OFFSET / FETCH appended after the main FROM block."""
    pattern = re.compile(
        r"\b(ORDER\s+BY|OFFSET|FETCH\s+NEXT)\b",
        re.IGNORECASE,
    )
    match = pattern.search(from_sql)
    if match:
        return from_sql[: match.start()].rstrip()
    return from_sql.rstrip()


def _extract_from_join_tables(from_sql: str) -> list[TableRef]:
    """Walk a FROM clause and collect every table referenced by FROM / JOIN."""
    parsed = sqlparse.parse(from_sql)
    if not parsed:
        return []

    tokens = parsed[0].tokens
    tables: list[TableRef] = []
    i = 0
    join_modifiers = {"INNER", "LEFT", "RIGHT", "FULL", "OUTER", "CROSS"}
    stop_keywords = {"WHERE", "GROUP", "HAVING", "ORDER", "UNION", "INTERSECT", "EXCEPT"}

    while i < len(tokens):
        token = tokens[i]
        if token.ttype is Keyword and token.normalized in stop_keywords:
            break
        if token.ttype is Keyword and token.normalized in {"FROM", "JOIN"}:
            i += 1
            while i < len(tokens) and tokens[i].ttype is Keyword and tokens[i].normalized in join_modifiers:
                i += 1
            while i < len(tokens) and tokens[i].is_whitespace:
                i += 1
            if i < len(tokens):
                _extract_tables_from_token(tokens[i], tables)
                i += 1
            continue
        if token.ttype is Keyword and token.normalized == "ON":
            i += 1
            while i < len(tokens):
                if tokens[i].ttype is Keyword and tokens[i].normalized in {"JOIN", *stop_keywords}:
                    break
                i += 1
            continue
        i += 1
    return tables


def extract_table_refs(sql: str) -> list[TableRef]:
    """Return unique table references from FROM / JOIN clauses."""
    from_sql = get_from_clause(sql)
    tables = _extract_from_join_tables(from_sql)

    seen: set[tuple[str, str, str]] = set()
    unique: list[TableRef] = []
    for ref in tables:
        key = (ref.schema, ref.table, ref.alias)
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    if not unique:
        raise ValueError("No tables found in query")
    return unique


def get_from_clause(sql: str, *, preserve_order_by: bool = False) -> str:
    """Return the FROM ... portion of a SELECT (without trailing ORDER BY unless requested)."""
    parsed = sqlparse.parse(sql.strip().rstrip(";"))
    if not parsed:
        raise ValueError("Empty SQL query")

    statement = parsed[0]
    from_idx = _find_from_index(statement.tokens)
    if from_idx is None:
        raise ValueError("Query must contain a FROM clause")

    from_sql = "".join(token.value for token in statement.tokens[from_idx:])
    if preserve_order_by:
        return from_sql.rstrip()
    return _trim_trailing_query_clauses(from_sql)


def build_table_select(sql: str, table_ref: TableRef) -> str:
    """Build a per-table SELECT query preserving joins/filters and TOP limit."""
    top_limit = extract_top_limit(sql)
    from_clause = get_from_clause(sql, preserve_order_by=top_limit is not None)
    prefix = table_ref.select_prefix
    if top_limit is not None:
        return f"SELECT TOP ({top_limit}) {prefix}.* {from_clause}"
    return f"SELECT DISTINCT {prefix}.* {from_clause}"


def validate_select_only(sql: str) -> str:
    """Ensure the query is a single read-only SELECT statement."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise ValueError("Query is empty")

    statements = [stmt for stmt in sqlparse.parse(stripped) if str(stmt).strip()]
    if len(statements) != 1:
        raise ValueError("Only a single SELECT statement is allowed")

    statement = statements[0]
    stmt_type = statement.get_type()
    if stmt_type != "SELECT":
        raise ValueError("Only SELECT queries are allowed")

    if re.search(r"\bSELECT\b[\s\S]*\bINTO\b", stripped, re.IGNORECASE):
        raise ValueError("SELECT INTO is not allowed")

    cleaned = sqlparse.format(stripped, strip_comments=True)
    forbidden = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|MERGE|EXEC|EXECUTE|ALTER|CREATE|"
        r"GRANT|REVOKE|DENY|BACKUP|RESTORE|DBCC|BULK)\b",
        re.IGNORECASE,
    )
    if forbidden.search(cleaned):
        raise ValueError("Only SELECT queries are allowed")

    if _find_from_index(statement.tokens) is None:
        raise ValueError("Query must contain a FROM clause")

    return stripped


def wrap_preview_query(sql: str, limit: int) -> str:
    """Wrap user query for preview with a row cap."""
    stripped = validate_select_only(sql)
    if re.search(r"\bTOP\s+\(?\s*\d+", stripped, re.IGNORECASE):
        return stripped
    return f"SELECT TOP ({limit}) * FROM ({stripped}) AS _preview"

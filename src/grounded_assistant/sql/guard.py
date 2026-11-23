"""Run model-generated SQL safely and return it with its evidence.

An LLM will write the SQL in the next phase. We never trust it. Four layers
of defence, each enough on its own to stop a write:

1. The database is opened read-only.
2. Only one statement may run (no "SELECT 1; DROP TABLE sales").
3. A SQLite authorizer approves every single operation: only SELECT and
   reads of tables the role is allowed to see. Everything else is denied.
4. Row filters are enforced with temporary views, so a restricted role
   cannot see other rows even with clever SQL.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from grounded_assistant.sql.policies import Role

# Operations an analytical query legitimately needs.
_ALWAYS_ALLOWED = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_FUNCTION,  # SUM, COUNT, strftime, ...
}


# Readable names for SQLite's numeric action codes, e.g. 9 -> "DELETE".
_ACTION_NAMES = {
    getattr(sqlite3, f"SQLITE_{name}"): name
    for name in [
        "INSERT", "UPDATE", "DELETE", "PRAGMA", "ATTACH", "DETACH", "TRANSACTION",
        "CREATE_TABLE", "CREATE_VIEW", "CREATE_INDEX", "CREATE_TRIGGER",
        "DROP_TABLE", "DROP_VIEW", "DROP_INDEX", "DROP_TRIGGER", "ALTER_TABLE",
    ]
}


class QueryRejected(Exception):
    """The query broke a rule. The message says which one."""


@dataclass
class QueryResult:
    """The answer data plus the evidence of where it came from."""

    sql: str
    role: str
    columns: list[str]
    rows: list[tuple]
    truncated: bool
    tables_read: set[str] = field(default_factory=set)
    columns_read: set[str] = field(default_factory=set)

    @property
    def row_count(self) -> int:
        return len(self.rows)


class SQLGuard:
    def __init__(self, db_path: str | Path, max_rows: int = 200):
        self.db_path = Path(db_path)
        self.max_rows = max_rows

    def _connect(self, role: Role) -> sqlite3.Connection:
        # Layer 1: read-only at the database level.
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)

        # Layer 4: a TEMP view with the same name shadows the real table,
        # so "FROM sales" silently means "FROM sales WHERE <filter>".
        for table, condition in role.row_filters.items():
            conn.execute(
                f"CREATE TEMP VIEW {table} AS "
                f"SELECT * FROM main.{table} WHERE {condition}"
            )
        return conn

    def run(self, sql: str, role: Role) -> QueryResult:
        sql = sql.strip().rstrip(";").strip()
        if not sql:
            raise QueryRejected("Empty query.")

        tables_read: set[str] = set()
        columns_read: set[str] = set()
        denied: list[str] = []

        def authorizer(action, arg1, arg2, db_name, via_view):
            # Layer 3: called by SQLite for every operation in the query.
            if action in _ALWAYS_ALLOWED:
                return sqlite3.SQLITE_OK

            if action == sqlite3.SQLITE_READ:
                table, column = arg1, arg2
                if table not in role.tables:
                    denied.append(f"table '{table}' is not allowed for role '{role.name}'")
                    return sqlite3.SQLITE_DENY

                filtered = table in role.row_filters
                if filtered and db_name == "main" and via_view != table:
                    # Direct access like "FROM main.sales" would skip the filter.
                    denied.append(f"direct access to main.{table} bypasses row security")
                    return sqlite3.SQLITE_DENY

                if db_name == "main":
                    tables_read.add(table)
                    columns_read.add(f"{table}.{column}")
                return sqlite3.SQLITE_OK

            denied.append(f"operation not allowed: {_ACTION_NAMES.get(action, action)}")
            return sqlite3.SQLITE_DENY

        conn = self._connect(role)
        conn.set_authorizer(authorizer)
        try:
            cursor = conn.execute(sql)  # Layer 2: execute() runs ONE statement only
            rows = cursor.fetchmany(self.max_rows + 1)
            columns = [d[0] for d in cursor.description or []]
        except sqlite3.ProgrammingError as exc:
            raise QueryRejected(f"Only a single statement is allowed: {exc}") from exc
        except sqlite3.DatabaseError as exc:
            reason = denied[0] if denied else str(exc)
            raise QueryRejected(reason) from exc
        finally:
            conn.close()

        truncated = len(rows) > self.max_rows
        return QueryResult(
            sql=sql,
            role=role.name,
            columns=columns,
            rows=rows[: self.max_rows],
            truncated=truncated,
            tables_read=tables_read,
            columns_read=columns_read,
        )

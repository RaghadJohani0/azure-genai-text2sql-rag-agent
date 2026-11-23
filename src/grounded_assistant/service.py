"""Ties the pieces together: role check -> guarded query -> audit entry.

In the next phase `question -> SQL` is done by an LLM. For now the SQL is
passed in directly, so every safety rule can be tested without a model.
"""

from __future__ import annotations

import time

from grounded_assistant.audit import AuditLog
from grounded_assistant.sql.guard import QueryRejected, QueryResult, SQLGuard
from grounded_assistant.sql.policies import get_role


class DataService:
    def __init__(self, guard: SQLGuard, audit: AuditLog):
        self.guard = guard
        self.audit = audit

    def query(self, user: str, role_name: str, question: str, sql: str) -> QueryResult:
        started = time.perf_counter()
        base = {"user": user, "role": role_name, "question": question, "sql": sql}

        try:
            role = get_role(role_name)
            result = self.guard.run(sql, role)
        except (QueryRejected, PermissionError) as exc:
            self.audit.record(**base, status="rejected", reason=str(exc),
                              duration_ms=_ms(started))
            raise

        self.audit.record(
            **base,
            status="ok",
            row_count=result.row_count,
            truncated=result.truncated,
            tables_read=result.tables_read,
            columns_read=result.columns_read,
            duration_ms=_ms(started),
        )
        return result


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)

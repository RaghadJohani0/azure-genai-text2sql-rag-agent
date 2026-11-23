"""Who may read what.

Each role lists the tables it may read and, optionally, a row filter per table.
A row filter is applied as row-level security: the role only ever sees the
rows that match it, whatever SQL is written.

In Azure this maps to Unity Catalog grants and row filters on Databricks,
or Entra ID groups mapped to roles.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Role:
    name: str
    tables: frozenset[str]
    row_filters: dict[str, str] = field(default_factory=dict)  # table -> SQL condition


ROLES: dict[str, Role] = {
    "finance_admin": Role(
        name="finance_admin",
        tables=frozenset({"sales", "products"}),
    ),
    "riyadh_manager": Role(
        name="riyadh_manager",
        tables=frozenset({"sales"}),  # no access to products (it holds unit_cost)
        row_filters={"sales": "region = 'Riyadh'"},
    ),
}


def get_role(name: str) -> Role:
    try:
        return ROLES[name]
    except KeyError:
        raise PermissionError(f"Unknown role: {name!r}") from None

import pytest

from grounded_assistant.sql.guard import QueryRejected
from grounded_assistant.sql.policies import get_role

ADMIN = get_role("finance_admin")
RIYADH = get_role("riyadh_manager")


# ---------- allowed queries ----------

def test_admin_can_aggregate_and_join(guard):
    result = guard.run(
        """
        SELECT p.category, SUM(s.revenue) AS revenue
        FROM sales s JOIN products p ON p.product = s.product
        GROUP BY p.category ORDER BY revenue DESC
        """,
        ADMIN,
    )
    assert result.columns == ["category", "revenue"]
    assert result.row_count == 3
    assert result.tables_read == {"sales", "products"}  # evidence of sources


def test_evidence_lists_columns_read(guard):
    result = guard.run("SELECT region, SUM(revenue) FROM sales GROUP BY region", ADMIN)
    assert {"sales.region", "sales.revenue"} <= result.columns_read


# ---------- row-level security ----------

def test_riyadh_manager_only_sees_riyadh_rows(guard):
    result = guard.run("SELECT DISTINCT region FROM sales", RIYADH)
    assert result.rows == [("Riyadh",)]


def test_row_filter_cannot_be_bypassed_with_or(guard):
    result = guard.run("SELECT DISTINCT region FROM sales WHERE 1=1 OR region='Jeddah'", RIYADH)
    assert result.rows == [("Riyadh",)]


def test_direct_main_table_access_is_denied(guard):
    with pytest.raises(QueryRejected, match="bypasses row security"):
        guard.run("SELECT DISTINCT region FROM main.sales", RIYADH)


# ---------- table-level access ----------

def test_restricted_role_cannot_read_cost_table(guard):
    with pytest.raises(QueryRejected, match="table 'products' is not allowed"):
        guard.run("SELECT product, unit_cost FROM products", RIYADH)


def test_cannot_read_schema_catalog(guard):
    with pytest.raises(QueryRejected):
        guard.run("SELECT sql FROM sqlite_master", RIYADH)


# ---------- writes and dangerous statements ----------

@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM sales",
        "UPDATE sales SET revenue = 0",
        "INSERT INTO sales (id) VALUES (999999)",
        "DROP TABLE sales",
        "PRAGMA table_info(sales)",
        "ATTACH DATABASE 'x.db' AS x",
        "CREATE TABLE hacked (a)",
    ],
)
def test_non_select_statements_are_rejected(guard, sql):
    with pytest.raises(QueryRejected):
        guard.run(sql, ADMIN)


def test_multiple_statements_are_rejected(guard):
    with pytest.raises(QueryRejected, match="single statement"):
        guard.run("SELECT 1; DROP TABLE sales", ADMIN)


def test_data_is_unchanged_after_attacks(guard):
    before = guard.run("SELECT COUNT(*) FROM sales", ADMIN).rows
    for sql in ["DELETE FROM sales", "SELECT 1; DELETE FROM sales"]:
        with pytest.raises(QueryRejected):
            guard.run(sql, ADMIN)
    assert guard.run("SELECT COUNT(*) FROM sales", ADMIN).rows == before


# ---------- limits ----------

def test_large_results_are_truncated(guard):
    result = guard.run("SELECT * FROM sales", ADMIN)
    assert result.row_count == 50
    assert result.truncated is True


def test_empty_query_rejected(guard):
    with pytest.raises(QueryRejected, match="Empty"):
        guard.run("  ;  ", ADMIN)

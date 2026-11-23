import pytest

from grounded_assistant.sql.guard import QueryRejected


def test_successful_query_is_audited_with_evidence(service):
    service.query(
        user="sara",
        role_name="riyadh_manager",
        question="Total revenue in Riyadh?",
        sql="SELECT SUM(revenue) FROM sales",
    )
    [entry] = service.audit.read_all()
    assert entry["status"] == "ok"
    assert entry["user"] == "sara"
    assert entry["tables_read"] == ["sales"]
    assert "timestamp" in entry


def test_rejected_query_is_audited_with_reason(service):
    with pytest.raises(QueryRejected):
        service.query("sara", "riyadh_manager", "What are our margins?",
                      "SELECT unit_cost FROM products")
    [entry] = service.audit.read_all()
    assert entry["status"] == "rejected"
    assert "products" in entry["reason"]


def test_unknown_role_is_rejected_and_audited(service):
    with pytest.raises(PermissionError):
        service.query("x", "ceo", "anything", "SELECT 1")
    assert service.audit.read_all()[0]["status"] == "rejected"

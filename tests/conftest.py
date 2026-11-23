import pytest

from grounded_assistant.audit import AuditLog
from grounded_assistant.data.seed import create_demo_db
from grounded_assistant.service import DataService
from grounded_assistant.sql.guard import SQLGuard


@pytest.fixture
def db_path(tmp_path):
    return create_demo_db(tmp_path / "demo.db", n_rows=300)


@pytest.fixture
def guard(db_path):
    return SQLGuard(db_path, max_rows=50)


@pytest.fixture
def service(guard, tmp_path):
    return DataService(guard, AuditLog(tmp_path / "audit.jsonl"))

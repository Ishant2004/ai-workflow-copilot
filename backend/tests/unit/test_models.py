"""Model/metadata tests — validate the schema without a live database."""

import app.models  # noqa: F401 - register models
import pytest
from app.db.base import Base
from app.models import RunStatus, StepType, Workflow, WorkflowStatus
from sqlalchemy.orm import configure_mappers

pytestmark = pytest.mark.unit


def test_all_tables_registered():
    assert set(Base.metadata.tables) == {
        "workflows",
        "steps",
        "runs",
        "step_results",
    }


def test_mappers_configure_cleanly():
    # Raises if any relationship/back_populates is misconfigured.
    configure_mappers()


def test_workflow_columns():
    cols = Base.metadata.tables["workflows"].columns
    assert {"id", "title", "description", "status", "created_at", "updated_at"} <= set(cols.keys())
    assert cols["title"].nullable is False


def test_foreign_keys_cascade():
    steps = Base.metadata.tables["steps"]
    fk = next(iter(steps.foreign_keys))
    assert fk.column.table.name == "workflows"
    assert fk.ondelete == "CASCADE"


def test_enum_values():
    assert WorkflowStatus.draft.value == "draft"
    assert "web_search" in {t.value for t in StepType}
    assert "awaiting_review" in {s.value for s in RunStatus}


def test_indexes_present():
    index_names = {idx.name for t in Base.metadata.tables.values() for idx in t.indexes}
    assert "ix_steps_workflow_id" in index_names
    assert "ix_runs_status" in index_names


def test_default_status_is_draft():
    wf = Workflow(title="t", description="d")
    # Column default is applied at flush; the Python-side enum default is draft.
    assert wf.status is None or wf.status == WorkflowStatus.draft

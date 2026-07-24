"""Human-in-the-loop review tests: approve / edit / reject a paused run."""

import uuid

import pytest

pytestmark = pytest.mark.unit


def _create_and_run(client) -> dict:
    wf = client.post(
        "/api/workflows", json={"task_description": "collect AI news and Slack me"}
    ).json()
    run = client.post(f"/api/workflows/{wf['id']}/runs").json()
    assert run["status"] == "awaiting_review"
    return run


def test_approve_runs_remaining_side_effecting_steps(workflow_client):
    run = _create_and_run(workflow_client)
    resp = workflow_client.post(f"/api/runs/{run['id']}/approve")
    assert resp.status_code == 200, resp.text
    approved = resp.json()
    assert approved["status"] == "succeeded"
    assert len(approved["step_results"]) == 3  # notify now executed
    assert approved["step_results"][2]["output"]["channel"] == "#general"


def test_reject_cancels_without_side_effects(workflow_client):
    run = _create_and_run(workflow_client)
    resp = workflow_client.post(f"/api/runs/{run['id']}/reject")
    assert resp.status_code == 200
    rejected = resp.json()
    assert rejected["status"] == "rejected"
    assert len(rejected["step_results"]) == 2  # notify never ran


def test_edit_then_approve_uses_edited_output(workflow_client):
    run = _create_and_run(workflow_client)
    # the summarize step is the 2nd result
    summarize_result = run["step_results"][1]
    edit = workflow_client.patch(
        f"/api/runs/{run['id']}/steps/{summarize_result['id']}",
        json={"output": {"summary": "EDITED DIGEST"}},
    )
    assert edit.status_code == 200
    approved = workflow_client.post(f"/api/runs/{run['id']}/approve").json()
    # notify consumed the edited summary from the rebuilt context
    assert "EDITED DIGEST" in approved["step_results"][2]["output"]["message_preview"]


def test_approve_non_reviewable_run_conflicts(workflow_client):
    # a workflow with no side-effecting steps runs to completion → not reviewable
    wf = workflow_client.post(
        "/api/workflows",
        json={
            "task_description": "just search",
            "plan": {
                "title": "search only",
                "summary": "s",
                "steps": [
                    {
                        "type": "web_search",
                        "name": "S",
                        "description": "d",
                        "config": {"query": "x"},
                    }
                ],
            },
        },
    ).json()
    run = workflow_client.post(f"/api/workflows/{wf['id']}/runs").json()
    assert run["status"] == "succeeded"
    resp = workflow_client.post(f"/api/runs/{run['id']}/approve")
    assert resp.status_code == 409


def test_review_actions_404_for_unknown_run(workflow_client):
    assert workflow_client.post(f"/api/runs/{uuid.uuid4()}/approve").status_code == 404
    assert workflow_client.post(f"/api/runs/{uuid.uuid4()}/reject").status_code == 404


def test_edit_unknown_step_result_404(workflow_client):
    run = _create_and_run(workflow_client)
    resp = workflow_client.patch(
        f"/api/runs/{run['id']}/steps/{uuid.uuid4()}",
        json={"output": {"summary": "x"}},
    )
    assert resp.status_code == 404

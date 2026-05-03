import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["GATEWAY_DB_PATH"] = str(Path(__file__).with_suffix(".sqlite"))

from app.main import app, reset_state  # noqa: E402


client = TestClient(app)


def setup_function() -> None:
    os.environ.pop("GATEWAY_API_KEY", None)
    reset_state()


def test_health_reports_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "storage": "sqlite",
        "documents": 0,
        "deployments": 0,
        "eval_runs": 0,
        "audit_events": 0,
    }


def test_ingest_and_ask_returns_retrieved_source() -> None:
    ingest = client.post(
        "/ingest",
        json={
            "documents": [
                {
                    "id": "teachclaw",
                    "text": "TeachClaw routes teacher requests into worksheets, PPTs, marking, and feedback.",
                }
            ]
        },
    )
    assert ingest.status_code == 200

    answer = client.post("/ask", json={"question": "What does TeachClaw route?"})

    assert answer.status_code == 200
    payload = answer.json()
    assert payload["sources"][0]["id"] == "teachclaw"
    assert "worksheets" in payload["answer"]


def test_eval_marks_expected_terms() -> None:
    client.post(
        "/ingest",
        json={
            "documents": [
                {
                    "id": "openclaw",
                    "text": "OpenClaw provides gateway sessions, plugins, skills, memory, and validation lanes.",
                }
            ]
        },
    )

    response = client.post(
        "/eval/run",
        json={"cases": [{"question": "What does OpenClaw provide?", "expected_terms": ["gateway", "memory"]}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["passed"] == 1
    assert payload["status"] == "pass"
    assert payload["run_id"] == "eval-1"


def test_eval_can_require_source_ids() -> None:
    client.post(
        "/ingest",
        json={
            "documents": [
                {
                    "id": "teachclaw",
                    "text": "TeachClaw deploys teacher workflows through OpenClaw and validates artifacts.",
                }
            ]
        },
    )

    response = client.post(
        "/eval/run",
        json={
            "cases": [
                {
                    "question": "What validates artifacts?",
                    "expected_terms": ["artifacts"],
                    "expected_source_ids": ["teachclaw"],
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["source_ids"] == ["teachclaw"]


def test_readiness_blocks_until_deployment_docs_and_evals_exist() -> None:
    response = client.get("/deployments/teachclaw-local/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "block"
    assert "Deployment profile is missing." in payload["blockers"]


def test_readiness_passes_when_profile_docs_and_evals_are_good() -> None:
    register = client.post(
        "/deployments/register",
        json={
            "name": "TeachClaw",
            "environment": "local",
            "owner": "Anas Abdi",
            "rollback_plan": "Revert to last validated route bundle and rerun gateway smoke tests.",
            "risk_notes": ["Artifact contracts can drift across runtime layers."],
            "required_eval_pass_rate": 1.0,
        },
    )
    assert register.status_code == 200
    deployment_id = register.json()["deployment_id"]

    client.post(
        "/ingest",
        json={
            "documents": [
                {
                    "id": "openclaw",
                    "text": "OpenClaw gateway smoke tests validate routing, memory, and artifact behavior.",
                    "tags": ["gateway", "evals"],
                }
            ]
        },
    )
    client.post(
        "/eval/run",
        json={"cases": [{"question": "What validates routing?", "expected_terms": ["gateway", "routing"]}]},
    )

    response = client.get(f"/deployments/{deployment_id}/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["eval_pass_rate"] == 1.0
    assert payload["last_eval_run_id"] == "eval-1"


def test_metrics_summarise_eval_state() -> None:
    client.post(
        "/ingest",
        json={"documents": [{"id": "sparkassist", "text": "SparkAssist extracts field notes into reports."}]},
    )
    client.post(
        "/eval/run",
        json={"cases": [{"question": "What extracts field notes?", "expected_terms": ["SparkAssist"]}]},
    )

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.json() == {
        "documents": 1,
        "deployments": 0,
        "eval_runs": 1,
        "audit_events": 2,
        "storage": "sqlite",
        "last_eval_status": "pass",
        "last_eval_pass_rate": 1.0,
    }


def test_write_endpoints_can_require_api_key() -> None:
    os.environ["GATEWAY_API_KEY"] = "test-secret"

    unauthorized = client.post(
        "/ingest",
        json={"documents": [{"id": "teachclaw", "text": "TeachClaw routes teacher workflows."}]},
    )
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/ingest",
        headers={"X-API-Key": "test-secret"},
        json={"documents": [{"id": "teachclaw", "text": "TeachClaw routes teacher workflows."}]},
    )
    assert authorized.status_code == 200


def test_audit_events_record_write_activity() -> None:
    client.post(
        "/ingest",
        json={"documents": [{"id": "sparkassist", "text": "SparkAssist structures field notes."}]},
    )
    client.post(
        "/eval/run",
        json={"cases": [{"question": "What structures field notes?", "expected_terms": ["SparkAssist"]}]},
    )

    response = client.get("/audit/events")

    assert response.status_code == 200
    events = response.json()["events"]
    assert [event["event_type"] for event in events] == ["eval.run_recorded", "documents.ingested"]
    assert events[0]["payload"]["status"] == "pass"

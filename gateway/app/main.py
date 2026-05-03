from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Iterable, Iterator, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field


app = FastAPI(title="AI Deployment Gateway", version="0.3.0")
logger = logging.getLogger("ai_deployment_gateway")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


Environment = Literal["local", "staging", "production"]
ReadinessStatus = Literal["pass", "needs_judgement", "block"]
DB_PATH_ENV = "GATEWAY_DB_PATH"
API_KEY_ENV = "GATEWAY_API_KEY"


class Document(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class IngestRequest(BaseModel):
    documents: list[Document]


class IngestResponse(BaseModel):
    stored: int
    total: int


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)


class Source(BaseModel):
    id: str
    score: float
    text: str


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]


class EvalCase(BaseModel):
    question: str
    expected_terms: list[str] = Field(default_factory=list)
    expected_source_ids: list[str] = Field(default_factory=list)


class EvalRunRequest(BaseModel):
    cases: list[EvalCase]


class EvalCaseResult(BaseModel):
    question: str
    passed: bool
    matched_terms: list[str]
    missing_terms: list[str]
    source_ids: list[str]


class EvalRunResponse(BaseModel):
    run_id: str
    status: ReadinessStatus
    passed: int
    failed: int
    results: list[EvalCaseResult]


class DeploymentProfile(BaseModel):
    name: str = Field(min_length=1)
    environment: Environment
    owner: str = Field(min_length=1)
    rollback_plan: str = Field(min_length=1)
    risk_notes: list[str] = Field(default_factory=list)
    required_eval_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)


class DeploymentRegistrationResponse(BaseModel):
    deployment_id: str
    registered_at: str
    profile: DeploymentProfile


class ReadinessReport(BaseModel):
    deployment_id: str
    status: ReadinessStatus
    eval_pass_rate: Optional[float]
    blockers: list[str]
    warnings: list[str]
    last_eval_run_id: Optional[str]


class MetricsResponse(BaseModel):
    documents: int
    deployments: int
    eval_runs: int
    audit_events: int
    storage: str
    last_eval_status: Optional[ReadinessStatus]
    last_eval_pass_rate: Optional[float]


class AuditEvent(BaseModel):
    id: int
    event_type: str
    resource_id: str
    payload: dict[str, object]
    created_at: str


class AuditEventsResponse(BaseModel):
    events: list[AuditEvent]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    return "-".join(tokenize(value)) or "deployment"


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def score_document(question_tokens: Counter[str], document_text: str) -> float:
    document_tokens = Counter(tokenize(document_text))
    overlap = sum(min(count, document_tokens[token]) for token, count in question_tokens.items())
    if overlap == 0:
        return 0.0
    return overlap / max(1, sum(question_tokens.values()))


def retrieve(question: str, top_k: int) -> list[Source]:
    question_tokens = Counter(tokenize(question))
    ranked: list[Source] = []
    with db_connection() as connection:
        rows = connection.execute("SELECT id, text FROM documents ORDER BY id").fetchall()
    for row in rows:
        text = str(row["text"])
        score = score_document(question_tokens, text)
        if score > 0:
            ranked.append(Source(id=str(row["id"]), score=round(score, 4), text=text))
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[:top_k]


def joined_context(sources: Iterable[Source]) -> str:
    return " ".join(source.text for source in sources)


def eval_status(passed: int, total: int) -> ReadinessStatus:
    if total == 0:
        return "needs_judgement"
    if passed == total:
        return "pass"
    return "block"


def db_path() -> str:
    return os.getenv(DB_PATH_ENV, "data/gateway.db")


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    path = db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        ensure_schema(connection)
        yield connection
        connection.commit()
    finally:
        connection.close()


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            tags TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS deployments (
            deployment_id TEXT PRIMARY KEY,
            profile TEXT NOT NULL,
            registered_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS eval_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL UNIQUE,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


def reset_state() -> None:
    with db_connection() as connection:
        connection.execute("DELETE FROM audit_events")
        connection.execute("DELETE FROM eval_runs")
        connection.execute("DELETE FROM deployments")
        connection.execute("DELETE FROM documents")


def require_write_access(x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None) -> None:
    configured_key = os.getenv(API_KEY_ENV)
    if configured_key and x_api_key != configured_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")


def write_audit_event(event_type: str, resource_id: str, payload: dict[str, object]) -> None:
    created_at = utc_now()
    with db_connection() as connection:
        connection.execute(
            """
            INSERT INTO audit_events (event_type, resource_id, payload, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (event_type, resource_id, json.dumps(payload, sort_keys=True), created_at),
        )
    logger.info(
        json.dumps(
            {
                "event_type": event_type,
                "resource_id": resource_id,
                "created_at": created_at,
                "payload": payload,
            },
            sort_keys=True,
        )
    )


def document_count(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])


def deployment_count(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT COUNT(*) FROM deployments").fetchone()[0])


def eval_run_count(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT COUNT(*) FROM eval_runs").fetchone()[0])


def audit_event_count(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0])


def last_eval_run(connection: sqlite3.Connection) -> EvalRunResponse | None:
    row = connection.execute("SELECT payload FROM eval_runs ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    return EvalRunResponse.model_validate_json(row["payload"])


def get_deployment(connection: sqlite3.Connection, deployment_id: str) -> DeploymentProfile | None:
    row = connection.execute(
        "SELECT profile FROM deployments WHERE deployment_id = ?",
        (deployment_id,),
    ).fetchone()
    if row is None:
        return None
    return DeploymentProfile.model_validate_json(row["profile"])


@app.get("/health")
def health() -> dict[str, object]:
    with db_connection() as connection:
        return {
            "status": "ok",
            "storage": "sqlite",
            "documents": document_count(connection),
            "deployments": deployment_count(connection),
            "eval_runs": eval_run_count(connection),
            "audit_events": audit_event_count(connection),
        }


@app.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest, _: None = Depends(require_write_access)) -> IngestResponse:
    updated_at = utc_now()
    with db_connection() as connection:
        for document in request.documents:
            connection.execute(
                """
                INSERT INTO documents (id, text, tags, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    text = excluded.text,
                    tags = excluded.tags,
                    updated_at = excluded.updated_at
                """,
                (document.id, document.text, json.dumps(document.tags), updated_at),
            )
        total = document_count(connection)
    write_audit_event(
        "documents.ingested",
        "documents",
        {
            "stored": len(request.documents),
            "total": total,
            "document_ids": [document.id for document in request.documents],
        },
    )
    return IngestResponse(stored=len(request.documents), total=total)


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    sources = retrieve(request.question, request.top_k)
    if not sources:
        return AskResponse(answer="I do not have enough retrieved context to answer.", sources=[])
    context = joined_context(sources)
    answer = f"Based on the retrieved context: {context[:500]}"
    return AskResponse(answer=answer, sources=sources)


@app.post("/eval/run", response_model=EvalRunResponse)
def run_eval(request: EvalRunRequest, _: None = Depends(require_write_access)) -> EvalRunResponse:
    results: list[EvalCaseResult] = []
    for case in request.cases:
        sources = retrieve(case.question, top_k=3)
        context = joined_context(sources).lower()
        source_ids = [source.id for source in sources]
        matched_terms = [term for term in case.expected_terms if term.lower() in context]
        missing_terms = [term for term in case.expected_terms if term.lower() not in context]
        missing_sources = [source_id for source_id in case.expected_source_ids if source_id not in source_ids]
        results.append(
            EvalCaseResult(
                question=case.question,
                passed=not missing_terms and not missing_sources,
                matched_terms=matched_terms,
                missing_terms=[*missing_terms, *[f"source:{source_id}" for source_id in missing_sources]],
                source_ids=source_ids,
            )
        )
    passed = sum(1 for result in results if result.passed)
    with db_connection() as connection:
        run_number = eval_run_count(connection) + 1
    response = EvalRunResponse(
        run_id=f"eval-{run_number}",
        status=eval_status(passed, len(results)),
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )
    created_at = utc_now()
    with db_connection() as connection:
        connection.execute(
            "INSERT INTO eval_runs (run_id, payload, created_at) VALUES (?, ?, ?)",
            (response.run_id, response.model_dump_json(), created_at),
        )
    write_audit_event(
        "eval.run_recorded",
        response.run_id,
        {"status": response.status, "passed": response.passed, "failed": response.failed},
    )
    return response


@app.post("/deployments/register", response_model=DeploymentRegistrationResponse)
def register_deployment(
    profile: DeploymentProfile,
    _: None = Depends(require_write_access),
) -> DeploymentRegistrationResponse:
    deployment_id = f"{slugify(profile.name)}-{slugify(profile.environment)}"
    registered_at = utc_now()
    with db_connection() as connection:
        connection.execute(
            """
            INSERT INTO deployments (deployment_id, profile, registered_at)
            VALUES (?, ?, ?)
            ON CONFLICT(deployment_id) DO UPDATE SET
                profile = excluded.profile,
                registered_at = excluded.registered_at
            """,
            (deployment_id, profile.model_dump_json(), registered_at),
        )
    write_audit_event(
        "deployment.registered",
        deployment_id,
        {"environment": profile.environment, "required_eval_pass_rate": profile.required_eval_pass_rate},
    )
    return DeploymentRegistrationResponse(deployment_id=deployment_id, registered_at=registered_at, profile=profile)


@app.get("/deployments/{deployment_id}/readiness", response_model=ReadinessReport)
def readiness(deployment_id: str) -> ReadinessReport:
    with db_connection() as connection:
        profile = get_deployment(connection, deployment_id)
        documents = document_count(connection)
        eval_runs = eval_run_count(connection)
        last_eval = last_eval_run(connection)
    blockers: list[str] = []
    warnings: list[str] = []
    if profile is None:
        blockers.append("Deployment profile is missing.")
    if documents == 0:
        blockers.append("No documents have been ingested.")
    if eval_runs == 0:
        blockers.append("No eval run has been recorded.")

    eval_pass_rate = None
    if last_eval is not None:
        total = last_eval.passed + last_eval.failed
        eval_pass_rate = last_eval.passed / total if total else None
        if profile is not None and eval_pass_rate is not None and eval_pass_rate < profile.required_eval_pass_rate:
            blockers.append(
                f"Eval pass rate {eval_pass_rate:.2f} is below required threshold "
                f"{profile.required_eval_pass_rate:.2f}."
            )
        if last_eval.status == "needs_judgement":
            warnings.append("Last eval run needs human judgement.")

    status: ReadinessStatus
    if blockers:
        status = "block"
    elif warnings:
        status = "needs_judgement"
    else:
        status = "pass"

    return ReadinessReport(
        deployment_id=deployment_id,
        status=status,
        eval_pass_rate=eval_pass_rate,
        blockers=blockers,
        warnings=warnings,
        last_eval_run_id=last_eval.run_id if last_eval else None,
    )


@app.get("/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    with db_connection() as connection:
        last_eval = last_eval_run(connection)
        documents = document_count(connection)
        deployments = deployment_count(connection)
        eval_runs = eval_run_count(connection)
        audit_events = audit_event_count(connection)
    pass_rate = None
    if last_eval is not None:
        total = last_eval.passed + last_eval.failed
        pass_rate = last_eval.passed / total if total else None
    return MetricsResponse(
        documents=documents,
        deployments=deployments,
        eval_runs=eval_runs,
        audit_events=audit_events,
        storage="sqlite",
        last_eval_status=last_eval.status if last_eval else None,
        last_eval_pass_rate=pass_rate,
    )


@app.get("/audit/events", response_model=AuditEventsResponse)
def audit_events(limit: int = Query(default=25, ge=1, le=100)) -> AuditEventsResponse:
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, event_type, resource_id, payload, created_at
            FROM audit_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return AuditEventsResponse(
        events=[
            AuditEvent(
                id=int(row["id"]),
                event_type=str(row["event_type"]),
                resource_id=str(row["resource_id"]),
                payload=json.loads(row["payload"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]
    )

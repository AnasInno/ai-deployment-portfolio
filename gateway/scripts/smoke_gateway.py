from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE = ROOT / "sample" / "evidence.json"


class SmokeFailure(RuntimeError):
    pass


def send_json(method: str, base_url: str, path: str, payload: Optional[dict[str, Any]] = None, api_key: Optional[str] = None) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Anas-AI-Deployment-Gateway-Smoke/1.0",
    }
    if api_key:
        headers["X-API-Key"] = api_key
    req = request.Request(base_url.rstrip("/") + path, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=8) as response:
            text = response.read().decode("utf-8")
            return response.status, json.loads(text) if text else None
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        try:
            payload = json.loads(text) if text else None
        except json.JSONDecodeError:
            payload = text
        return exc.code, payload


def require_status(name: str, actual: int, expected: int) -> None:
    if actual != expected:
        raise SmokeFailure(f"{name} returned {actual}, expected {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a smoke check against the AI Deployment Gateway.")
    parser.add_argument("--base-url", default=os.getenv("GATEWAY_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("GATEWAY_API_KEY"))
    parser.add_argument("--sample", default=str(DEFAULT_SAMPLE))
    args = parser.parse_args()

    sample = json.loads(Path(args.sample).read_text(encoding="utf-8"))
    summary: dict[str, Any] = {"base_url": args.base_url, "checks": []}

    health_status, health = send_json("GET", args.base_url, "/health")
    require_status("health", health_status, 200)
    summary["checks"].append({"health": health})

    if args.api_key:
        unauth_status, unauth = send_json(
            "POST",
            args.base_url,
            "/ingest",
            {"documents": [{"id": "unauthorized-check", "text": "This should be rejected."}]},
        )
        require_status("unauthorized ingest", unauth_status, 401)
        summary["checks"].append({"unauthorized_ingest": unauth})

    ingest_status, ingest = send_json("POST", args.base_url, "/ingest", {"documents": sample["documents"]}, args.api_key)
    require_status("ingest", ingest_status, 200)
    summary["checks"].append({"ingest": ingest})

    ask_status, ask = send_json("POST", args.base_url, "/ask", {"question": sample["question"], "top_k": 3})
    require_status("ask", ask_status, 200)
    if not ask.get("sources"):
        raise SmokeFailure("ask returned no sources")
    summary["checks"].append({"ask_source_ids": [source["id"] for source in ask["sources"]]})

    register_status, register = send_json("POST", args.base_url, "/deployments/register", sample["deployment"], args.api_key)
    require_status("deployment registration", register_status, 200)
    deployment_id = register["deployment_id"]
    summary["checks"].append({"deployment_id": deployment_id})

    eval_status, eval_payload = send_json("POST", args.base_url, "/eval/run", sample["eval"], args.api_key)
    require_status("eval", eval_status, 200)
    if eval_payload["status"] != "pass":
        raise SmokeFailure(f"eval status was {eval_payload['status']}, expected pass")
    summary["checks"].append({"eval": {"run_id": eval_payload["run_id"], "status": eval_payload["status"]}})

    readiness_status, readiness = send_json("GET", args.base_url, f"/deployments/{deployment_id}/readiness")
    require_status("readiness", readiness_status, 200)
    if readiness["status"] != "pass":
        raise SmokeFailure(f"readiness status was {readiness['status']}, expected pass")
    summary["checks"].append({"readiness": readiness})

    metrics_status, metrics = send_json("GET", args.base_url, "/metrics")
    require_status("metrics", metrics_status, 200)
    summary["checks"].append({"metrics": metrics})

    audit_status, audit = send_json("GET", args.base_url, "/audit/events")
    require_status("audit events", audit_status, 200)
    event_types = [event["event_type"] for event in audit["events"]]
    for expected_event in ["documents.ingested", "deployment.registered", "eval.run_recorded"]:
        if expected_event not in event_types:
            raise SmokeFailure(f"audit event {expected_event} missing from {event_types}")
    summary["checks"].append({"audit_event_types": event_types[:5]})

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)

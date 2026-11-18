"""Convert a recent audit window into a Streamlit evaluation run."""

import argparse
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from baseline import classify
from blue_client import BlueClient, BlueError
from dashboard.domain import validate
from html_report import render_report

HERE = Path(__file__).resolve().parent
MAX_SCAN_BYTES = 2 * 1024 * 1024
FIXED_ROUTES = {
    "/api/accounts", "/api/accounts/me", "/api/auth/customer/login",
    "/api/auth/staff/login", "/api/auth/logout", "/api/customers/me",
    "/api/customers/signup", "/api/staff/customers", "/api/staff/audit-logs",
    "/api/staff/me", "/api/staff/users", "/api/transfers", "/api/lab",
    "/api/admin/security/events",
}
PARAMETER_ROUTES = {
    "/api/accounts/{account_id}/verify-pin", "/api/accounts/{account_id}/transactions",
    "/api/customers/{customer_id}", "/api/staff/customers/{customer_id}",
    "/api/staff/customers/{customer_id}/accounts", "/api/staff/users/{staff_id}",
}
LEGACY_ROUTES = {
    re.compile(re.sub(r"\\\{[a-z_]+\\\}", lambda _: r"[0-9]+", re.escape(route))): route
    for route in PARAMETER_ROUTES
}
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


def clean_event(raw, number):
    if not isinstance(raw, dict):
        return None
    path, method, status = raw.get("path"), raw.get("method"), raw.get("status")
    if not isinstance(path, str) or not isinstance(method, str) or method not in METHODS:
        return None
    if type(status) is not int or not 100 <= status <= 599:
        return None
    if path not in FIXED_ROUTES and path not in PARAMETER_ROUTES:
        path = next((route for pattern, route in LEGACY_ROUTES.items() if pattern.fullmatch(path)),
                    "/api/{unmatched}") if len(path) <= 120 else "/api/{unmatched}"
    event = {"event_id": f"E{number}", "method": method, "path": path, "status": status}
    stamp = raw.get("timestamp")
    if isinstance(stamp, str) and len(stamp) <= 40:
        try:
            event["timestamp"] = datetime.fromisoformat(stamp).isoformat()
        except ValueError:
            pass
    for field in ("client", "principal", "auth_subject"):
        value = raw.get(field)
        if isinstance(value, str) and re.fullmatch("[0-9a-f]{16}", value):
            event[field] = value
    for field, allowed in {
        "auth_role": {"CUSTOMER", "STAFF", "ADMIN"},
        "required_role": {"LOGIN", "CUSTOMER", "STAFF_OR_ADMIN", "ADMIN", "ACCOUNT_OWNER"},
        "auth_state": {"anonymous", "unverified", "verified"},
        "authz_decision": {"allowed", "denied", "rate_limited_backend"},
    }.items():
        value = raw.get(field)
        if isinstance(value, str) and value in allowed:
            event[field] = value
    return event


def recent_events(path, limit):
    with path.open("rb") as source:
        end = source.seek(0, 2)
        start = max(0, end - MAX_SCAN_BYTES)
        source.seek(start)
        window = source.read(end - start)
    lines = window.splitlines()
    if start:
        lines = lines[1:]
    if window and not window.endswith(b"\n"):
        lines = lines[:-1]
    events = deque(maxlen=limit)
    for index, line in enumerate(lines, 1):
        try:
            event = clean_event(json.loads(line), index)
        except (ValueError, UnicodeError, RecursionError):
            continue
        if event is not None:
            events.append(event)
    return list(events)


def analyze_window(events, client, batch_size):
    findings_by_event = {}
    notes = []
    assessments = []
    for index in range(0, len(events), batch_size):
        window = events[index:index + batch_size]
        print(f"블루 분석 중: {window[0]['event_id']}–{window[-1]['event_id']}")
        answer = client.analyze(window)
        print(f"블루 판단: {answer['classification']} / {answer['severity']}")
        assessments.append(answer)
        notes.append(answer["limitations"])
        if answer["classification"] == "suspicious":
            if not answer["evidence_ids"]:
                raise BlueError("의심 판단에 근거 로그 ID가 없습니다.")
            for event_id in answer["evidence_ids"]:
                findings_by_event[event_id] = answer
        elif answer["classification"] == "uncertain":
            notes.append("일부 로그 묶음은 블루 모델이 판단을 보류했습니다.")
    return findings_by_event, list(dict.fromkeys(notes)), assessments


def build_evaluation(events, run_id, now, client, batch_size):
    blue, notes, assessments = {}, [], []
    status = "pending"
    if client is None:
        notes.append("기본 검사만 실행했습니다. 블루 모델 분석은 대기 중입니다.")
    else:
        try:
            print(f"모델 API에서 확인한 ID: {client.discover()}")
            blue, notes, assessments = analyze_window(events, client, batch_size)
            status = "completed"
        except BlueError as error:
            status = "failed"
            notes.append(str(error))

    findings, logs = [], []
    for event in events:
        event_id = event["event_id"]
        logs.append({"log_id": event_id, **{k: v for k, v in event.items() if k != "event_id"}})
        rule, answer = classify(event), blue.get(event_id)
        if not (rule or answer):
            continue
        reason = " ".join([rule[3] if rule else "", answer["summary"] if answer else ""]).strip()
        findings.append({
            "finding_id": f"F-{event_id}",
            "title": rule[2] if rule else "블루 추가 의심",
            "reason": reason,
            "severity": answer["severity"] if answer else rule[1],
            "baseline_detected": rule is not None,
            "blue_detected": answer is not None,
            "validation": "pending",
            "evidence_log_ids": list(dict.fromkeys(answer["evidence_ids"])) if answer else [event_id],
            "recommendations": answer["recommended_actions"] if answer else [],
            "uncertainties": [answer["limitations"]] if answer else [],
            "time": event.get("timestamp", ""),
        })

    return validate({
        "schema_version": "1.0",
        "run_id": run_id,
        "title": "FinLab 은행 API 감사 로그",
        "updated_at": now.isoformat(timespec="seconds"),
        "analysis_status": status,
        "model_name": (client.model or client.cfg["model"]) if client else "",
        "analysis_notes": notes,
        "findings": findings,
        "logs": logs,
        "blue_assessments": assessments,
    })


def write_evaluation(root, data):
    folder = root / data["run_id"]
    folder.mkdir(parents=True, exist_ok=False)
    destination = folder / "evaluation.json"
    temp_path = folder / "evaluation.json.tmp"
    try:
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(destination)
    finally:
        temp_path.unlink(missing_ok=True)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=HERE.parent / "logs/security.jsonl")
    parser.add_argument("--runs", type=Path, default=HERE / "dashboard/runs")
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--source", choices=("docker", "file", "fixture"), default="file")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 100 or not 1 <= args.batch_size <= 16:
        parser.error("limit must be 1–100 and batch-size must be 1–16")

    try:
        events = recent_events(args.log, args.limit)
    except OSError as error:
        parser.exit(2, f"감사 로그를 읽을 수 없습니다: {error.filename or args.log}\n")
    if not events:
        parser.exit(2, "완료된 감사 로그가 없습니다. 은행 API를 사용한 뒤 다시 실행하세요.\n")

    client = None
    if not args.baseline_only:
        url = os.environ.get("FINLAB_BLUE_BASE_URL", "").strip()
        if not url:
            parser.error("FINLAB_BLUE_BASE_URL 또는 --baseline-only가 필요합니다.")
        client = BlueClient({
            "llm_base_url": url,
            "api_key_env": "FINLAB_BLUE_API_KEY",
            "model": os.environ.get("FINLAB_BLUE_MODEL", "openai/gpt-oss-20b"),
            "max_tokens": 2048,
        })
    now = datetime.now(timezone.utc)
    run_id = f"{now:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    data = build_evaluation(events, run_id, now, client, args.batch_size)
    data["data_source"] = args.source
    result = write_evaluation(args.runs, data)
    print(f"[{data['analysis_status']}] {result}")
    if args.html:
        report_dir = args.report_dir or result.parent
        report_dir.mkdir(parents=True, exist_ok=True)
        report = report_dir / f"report_{run_id}.html"
        temp = report.with_suffix(".html.tmp")
        try:
            temp.write_text(render_report(data), encoding="utf-8")
            temp.replace(report)
        finally:
            temp.unlink(missing_ok=True)
        print(f"결과 화면: {report}")
    for note in data["analysis_notes"]:
        print(note)
    return int(data["analysis_status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())

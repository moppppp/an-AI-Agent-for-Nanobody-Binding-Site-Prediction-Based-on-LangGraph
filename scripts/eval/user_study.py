#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
from common import DATASETS, OUTPUTS, ROOT  # noqa: E402
LOG = OUTPUTS / "user_study_log.jsonl"


def _append(row: dict) -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_all() -> list[dict]:
    if not LOG.is_file():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def cmd_start(args: argparse.Namespace) -> None:
    study_id = "nanobody_agent_pilot"
    tp = DATASETS / "user_study_tasks.json"
    if tp.is_file():
        study_id = json.loads(tp.read_text(encoding="utf-8")).get("study_id", study_id)
    sid = str(uuid.uuid4())[:8]
    _append({
        "session_id": sid,
        "event": "start",
        "ts": datetime.now(timezone.utc).isoformat(),
        "study_id": study_id,
        "participant_id": args.participant,
        "role": args.role,
        "mode": args.mode,
        "task_id": args.task,
    })
    print("session_id=" + sid)


def cmd_complete(args: argparse.Namespace) -> None:
    scores = {}
    for part in (args.scores or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            scores[k.strip()] = int(v.strip())
    _append({
        "session_id": args.session,
        "event": "complete",
        "ts": datetime.now(timezone.utc).isoformat(),
        "success": bool(args.success),
        "duration_seconds": args.seconds,
        "scores": scores,
        "feedback": args.feedback or "",
    })
    print("ok")


def cmd_report(_: argparse.Namespace) -> None:
    rows = _read_all()
    starts = {r["session_id"]: r for r in rows if r.get("event") == "start"}
    done = [r for r in rows if r.get("event") == "complete"]
    by_mode: dict[str, list] = {}
    for c in done:
        s = starts.get(c["session_id"], {})
        by_mode.setdefault(s.get("mode", "unknown"), []).append({**s, **c})
    report = {"sessions_completed": len(done), "by_mode": {}}
    for mode, items in by_mode.items():
        n = len(items)
        succ = sum(1 for i in items if i.get("success"))
        times = [i["duration_seconds"] for i in items if i.get("duration_seconds") is not None]
        report["by_mode"][mode] = {
            "count": n,
            "task_completion_rate_pct": round(100.0 * succ / n, 2) if n else 0,
            "avg_duration_seconds": round(sum(times) / len(times), 1) if times else None,
        }
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    (OUTPUTS / "user_study_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (OUTPUTS / "user_study_export.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["session_id", "mode", "role", "task_id", "success", "duration_seconds", "feedback"])
        for c in done:
            s = starts.get(c["session_id"], {})
            w.writerow([
                c.get("session_id"),
                s.get("mode"),
                s.get("role"),
                s.get("task_id"),
                c.get("success"),
                c.get("duration_seconds"),
                c.get("feedback"),
            ])
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("start")
    st.add_argument("--participant", required=True)
    st.add_argument(
        "--role",
        default="lab_student",
        choices=["lab_student", "advisor", "teacher", "open_day_visitor"],
    )
    st.add_argument("--mode", required=True, choices=["baseline_e2e", "agent_rag"])
    st.add_argument("--task", required=True)
    cp = sub.add_parser("complete")
    cp.add_argument("--session", required=True)
    cp.add_argument("--success", action="store_true")
    cp.add_argument("--seconds", type=int, default=None)
    cp.add_argument("--scores", default="")
    cp.add_argument("--feedback", default="")
    sub.add_parser("report")
    a = p.parse_args()
    {"start": cmd_start, "complete": cmd_complete, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()

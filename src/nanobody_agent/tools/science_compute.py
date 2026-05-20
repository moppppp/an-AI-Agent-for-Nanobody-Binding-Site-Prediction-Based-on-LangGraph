from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from nanobody_agent.config import Settings


def submit_science_job(
    settings: Settings,
    *,
    engine: str,
    pdb_path: str | None,
    mutations: list[str] | None = None,
) -> dict[str, Any]:
    """
    Submit async job to SLURM/K8s (stub records job manifest locally).
    Engines: rosetta | foldx | alphafold
    Returns job_id; poll via get_job_status.
    """
    engine = engine.lower().strip()
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    jobs_dir = settings.science_jobs_dir.resolve()
    jobs_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "job_id": job_id,
        "engine": engine,
        "scheduler": settings.job_scheduler,
        "pdb_path": pdb_path,
        "mutations": mutations or [],
        "status": "queued",
        "submitted_at": time.time(),
    }
    (jobs_dir / f"{job_id}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if settings.job_scheduler == "stub":
        _complete_stub_job(jobs_dir, job_id, engine)
        return get_job_status(settings, job_id)

    return manifest


def _complete_stub_job(jobs_dir: Path, job_id: str, engine: str) -> None:
    """Simulate finished job with plausible metrics."""
    metrics: dict[str, Any] = {
        "ddG_kcal_mol": round(-1.2, 2),
        "RMSD_A": round(1.05, 2),
        "interface_energy": round(-8.5, 2),
    }
    if engine == "foldx":
        metrics["ddG_kcal_mol"] = round(-2.1, 2)
    elif engine == "alphafold":
        metrics = {"plddt_mean": 88.5, "RMSD_A": 0.85, "pae_mean": 4.2}

    path = jobs_dir / f"{job_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "completed"
    data["completed_at"] = time.time()
    data["metrics"] = metrics
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_job_status(settings: Settings, job_id: str) -> dict[str, Any]:
    path = settings.science_jobs_dir / f"{job_id}.json"
    if not path.is_file():
        return {"found": False, "job_id": job_id}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_science_query(user_query: str) -> dict[str, Any]:
    engine = "rosetta"
    low = user_query.lower()
    if "foldx" in low:
        engine = "foldx"
    elif "alphafold" in low or "af2" in low:
        engine = "alphafold"
    elif "rosetta" in low:
        engine = "rosetta"
    mutations = re.findall(r"[A-Z]\d+[A-Z]", user_query)
    return {"engine": engine, "mutations": mutations}

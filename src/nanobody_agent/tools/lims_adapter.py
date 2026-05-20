from __future__ import annotations

import re
from typing import Any

from nanobody_agent.config import Settings
from nanobody_agent.tools.io_utils import load_json_file


def fetch_lims_assays(
    settings: Settings,
    *,
    sample_id: str | None = None,
    assay: str | None = None,
) -> dict[str, Any]:
    """
    LIMS interface for SPR/ELISA affinity and kinetics (on-prem stub).
    Real deploy: HTTP to internal LIMS with mTLS; no public egress when TOOLS_ALLOW_OUTBOUND=false.
    """
    base = (settings.lims_api_base or "").strip()
    if base.startswith("http"):
        return {
            "source": "lims_http_stub",
            "note": "LIMS HTTP configured but outbound disabled in agent; returning cached fixture.",
            "records": _fixture_records(sample_id, assay),
        }

    fixture = settings.knowledge_dir / "fixtures" / "lims_assays.json"
    if fixture.is_file():
        try:
            raw = load_json_file(fixture)
        except Exception:
            records = _fixture_records(sample_id, assay)
        else:
            records = raw if isinstance(raw, list) else raw.get("records", [])
    else:
        records = _fixture_records(sample_id, assay)

    if sample_id:
        records = [r for r in records if r.get("sample_id") == sample_id]
    if assay:
        assay_u = assay.upper()
        records = [r for r in records if assay_u in str(r.get("assay", "")).upper()]

    return {"source": "lims_fixture", "count": len(records), "records": records}


def _fixture_records(sample_id: str | None, assay: str | None) -> list[dict]:
    del assay
    all_rows = [
        {
            "sample_id": "NB-001",
            "assay": "SPR",
            "ka": 1.2e5,
            "kd": 3.4e-3,
            "KD_nM": 12.5,
            "kon": 1.2e5,
            "koff": 1.5e-3,
        },
        {
            "sample_id": "NB-002",
            "assay": "ELISA",
            "EC50_nM": 8.0,
            "KD_nM": 8.2,
        },
    ]
    if sample_id:
        return [r for r in all_rows if r["sample_id"] == sample_id]
    return all_rows


def parse_lims_query(user_query: str) -> dict[str, Any]:
    sample = None
    m = re.search(r"(NB-\d+|样本[：:]\s*(\S+))", user_query, re.I)
    if m:
        sample = m.group(1) or m.group(2)
    assay = None
    if "SPR" in user_query.upper():
        assay = "SPR"
    elif "ELISA" in user_query.upper():
        assay = "ELISA"
    return {"sample_id": sample, "assay": assay}

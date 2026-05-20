from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from nanobody_agent.config import Settings


def _ensure_demo_db(path: Path) -> None:
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE clones (
            clone_id TEXT PRIMARY KEY,
            target TEXT,
            cdr3 TEXT,
            affinity_kd_nm REAL,
            round INTEGER
        )
        """
    )
    rows = [
        ("NB-001", "PD-L1", "CAVSGGY", 12.5, 3),
        ("NB-002", "PD-L1", "CARGRDY", 8.2, 4),
        ("NB-003", "HER2", "CVYSSDY", 45.0, 2),
    ]
    conn.executemany(
        "INSERT INTO clones VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()


def query_phage_library(
    settings: Settings,
    *,
    target: str | None = None,
    max_kd_nm: float | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Internal phage display library — SQL dynamic query.
    Uses PHAGE_DB_URL (sqlite:///path) or demo DB under knowledge_base/demo_phage.db.
    """
    url = (settings.phage_db_url or "").strip()
    if url.startswith("sqlite:///"):
        db_path = Path(url.replace("sqlite:///", "", 1))
    else:
        db_path = settings.knowledge_dir / "demo_phage.db"

    _ensure_demo_db(db_path)
    clauses: list[str] = []
    params: list[Any] = []
    if target:
        clauses.append("target LIKE ?")
        params.append(f"%{target}%")
    if max_kd_nm is not None:
        clauses.append("affinity_kd_nm <= ?")
        params.append(max_kd_nm)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT clone_id, target, cdr3, affinity_kd_nm, round FROM clones{where} ORDER BY affinity_kd_nm ASC LIMIT ?"
    params.append(limit)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {
        "source": "phage_display_sql",
        "db": str(db_path),
        "sql": sql,
        "count": len(rows),
        "rows": rows,
    }


def parse_phage_query(user_query: str) -> dict[str, Any]:
    target = None
    m = re.search(r"(PD-?L1|HER2|CD[0-9]+|靶标[：:]\s*(\S+))", user_query, re.I)
    if m:
        target = m.group(1) or m.group(2)
    max_kd = None
    m2 = re.search(r"KD\s*[<≤]\s*(\d+(?:\.\d+)?)\s*nM", user_query, re.I)
    if m2:
        max_kd = float(m2.group(1))
    return {"target": target, "max_kd_nm": max_kd}

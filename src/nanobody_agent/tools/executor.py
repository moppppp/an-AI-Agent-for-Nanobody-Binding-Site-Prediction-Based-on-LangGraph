from __future__ import annotations

import time
from typing import Any

from nanobody_agent.config import Settings
from nanobody_agent.tools.audit import ToolAuditLog
from nanobody_agent.tools.lims_adapter import fetch_lims_assays, parse_lims_query
from nanobody_agent.tools.pdb_library import lookup_pdb, parse_pdb_query
from nanobody_agent.tools.phage_library import parse_phage_query, query_phage_library
from nanobody_agent.tools.registry import ToolRegistry, ToolSpec
from nanobody_agent.tools.science_compute import (
    get_job_status,
    parse_science_query,
    submit_science_job,
)


def _wrap_phage(settings: Settings, **kw: Any) -> dict[str, Any]:
    p = parse_phage_query(kw.get("user_query", ""))
    return query_phage_library(
        settings,
        target=p.get("target"),
        max_kd_nm=p.get("max_kd_nm"),
    )


def _wrap_lims(settings: Settings, **kw: Any) -> dict[str, Any]:
    p = parse_lims_query(kw.get("user_query", ""))
    return fetch_lims_assays(settings, sample_id=p.get("sample_id"), assay=p.get("assay"))


def _wrap_pdb(settings: Settings, **kw: Any) -> dict[str, Any]:
    p = parse_pdb_query(kw.get("user_query", ""))
    if not p.get("pdb_id"):
        return {"error": "未识别 PDB ID，请在问题中提供四位 ID（如 1ABC）"}
    return lookup_pdb(
        settings,
        pdb_id=p["pdb_id"],
        chain=p.get("chain"),
        partner_chain=p.get("partner_chain"),
    )


def _wrap_science(settings: Settings, **kw: Any) -> dict[str, Any]:
    p = parse_science_query(kw.get("user_query", ""))
    pdb_path = kw.get("pdb_path")
    manifest = submit_science_job(
        settings,
        engine=p["engine"],
        pdb_path=str(pdb_path) if pdb_path else None,
        mutations=p.get("mutations"),
    )
    if manifest.get("status") == "completed":
        return manifest
    return manifest


def build_registry(settings: Settings) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        ToolSpec(
            name="phage_library_sql",
            description="Internal phage display library (SQL)",
            handler=lambda **kw: _wrap_phage(settings, **kw),
            roles=frozenset({"default", "scientist"}),
        )
    )
    reg.register(
        ToolSpec(
            name="lims_spr_elisa",
            description="LIMS SPR/ELISA affinity and kinetics",
            handler=lambda **kw: _wrap_lims(settings, **kw),
            roles=frozenset({"default", "scientist"}),
        )
    )
    reg.register(
        ToolSpec(
            name="pdb_library_lookup",
            description="Local PDB ID lookup and residue contacts",
            handler=lambda **kw: _wrap_pdb(settings, **kw),
            roles=frozenset({"default", "scientist"}),
        )
    )
    reg.register(
        ToolSpec(
            name="science_compute_job",
            description="Rosetta/FoldX/AlphaFold via SLURM/K8s (async)",
            handler=lambda **kw: _wrap_science(settings, **kw),
            roles=frozenset({"scientist"}),
        )
    )
    return reg


def select_tools_for_query(user_query: str) -> list[str]:
    q = user_query
    tools: list[str] = []
    if any(k in q for k in ("噬菌体", "展示库", "克隆", "phage", "CDR3")):
        tools.append("phage_library_sql")
    if any(k in q.upper() for k in ("LIMS", "SPR", "ELISA", "动力学", "kon", "koff")):
        tools.append("lims_spr_elisa")
    if any(k in q.upper() for k in ("PDB", "结构库", "残基接触", "contact")) or _looks_like_pdb_id(q):
        tools.append("pdb_library_lookup")
    if any(
        k in q
        for k in (
            "Rosetta",
            "FoldX",
            "AlphaFold",
            "突变扫描",
            "亲和力成熟",
            "ddG",
            "RMSD",
            "SLURM",
            "作业",
        )
    ):
        tools.append("science_compute_job")
    return tools or ["phage_library_sql"]


def _looks_like_pdb_id(q: str) -> bool:
    import re

    return bool(re.search(r"\b[1-9][A-Za-z0-9]{3}\b", q))


class ToolExecutor:
    def __init__(self, settings: Settings, role: str | None = None) -> None:
        self.settings = settings
        self.role = (role or settings.tool_actor_role or "default").strip()
        self.registry = build_registry(settings)
        self.audit = ToolAuditLog(settings.tool_audit_dir)

    def invoke_all(
        self,
        user_query: str,
        *,
        actor: str = "agent",
        pdb_path: str | None = None,
    ) -> list[dict[str, Any]]:
        names = select_tools_for_query(user_query)
        results: list[dict[str, Any]] = []
        for name in names:
            results.append(
                self.invoke(
                    name,
                    user_query=user_query,
                    actor=actor,
                    pdb_path=pdb_path,
                )
            )
        return results

    def _fail(self, tool_name: str, message: str) -> dict[str, Any]:
        return {
            "tool": tool_name,
            "success": False,
            "audit_id": None,
            "result": {"error": message},
        }

    def invoke(self, tool_name: str, **kwargs: Any) -> dict[str, Any]:
        spec = self.registry.get(tool_name)
        if not spec:
            return self._fail(tool_name, "unknown tool")
        if not self.registry.allowed(tool_name, self.role):
            return self._fail(tool_name, f"permission denied (role={self.role})")
        if spec.outbound and not self.settings.tools_allow_outbound:
            return self._fail(tool_name, "outbound disabled (data stays on-prem)")

        t0 = time.perf_counter()
        err = None
        success = True
        try:
            payload = spec.handler(**kwargs)
            if payload.get("error"):
                success = False
                err = str(payload["error"])
        except Exception as e:
            payload = {"error": str(e)}
            success = False
            err = str(e)
        duration = (time.perf_counter() - t0) * 1000
        audit_id = self.audit.record(
            tool_name=tool_name,
            actor=kwargs.get("actor", "agent"),
            params={k: v for k, v in kwargs.items() if k != "user_query"},
            result_summary=str(payload)[:200],
            success=success,
            duration_ms=duration,
            error=err,
        )
        return {
            "tool": tool_name,
            "audit_id": audit_id,
            "success": success,
            "result": payload,
        }


def format_tool_answer(results: list[dict[str, Any]]) -> str:
    lines = ["## 领域工具调用结果", ""]
    for r in results:
        name = r.get("tool", "?")
        lines.append(f"### {name}")
        if r.get("audit_id"):
            lines.append(f"- 审计ID: `{r['audit_id']}`")
        if not r.get("success"):
            err = (r.get("result") or {}).get("error") or r.get("error") or "unknown"
            lines.append(f"- 失败: {err}")
            lines.append("")
            continue
        payload = r.get("result") or {}
        if name == "science_compute_job" and payload.get("metrics"):
            m = payload["metrics"]
            lines.append(f"- 作业: `{payload.get('job_id')}` 状态: {payload.get('status')}")
            for k, v in m.items():
                lines.append(f"- {k}: {v}")
        elif name == "phage_library_sql":
            for row in (payload.get("rows") or [])[:5]:
                lines.append(f"- {row}")
        elif name == "lims_spr_elisa":
            for row in (payload.get("records") or [])[:5]:
                lines.append(f"- {row}")
        elif name == "pdb_library_lookup":
            if payload.get("found"):
                lines.append(f"- PDB: {payload.get('pdb_id')} 链 {payload.get('chain_id')}")
                if payload.get("contacts"):
                    lines.append(f"- 接触对数: {len(payload['contacts'])} (展示前5条)")
                    for c in payload["contacts"][:5]:
                        lines.append(f"  - {c}")
            else:
                lines.append(f"- {payload.get('hint', payload)}")
        else:
            lines.append(f"- {payload}")
        lines.append("")
    lines.append(
        "_调用已写入本地审计日志；敏感数据默认不出域（TOOLS_ALLOW_OUTBOUND=false）。_"
    )
    return "\n".join(lines)

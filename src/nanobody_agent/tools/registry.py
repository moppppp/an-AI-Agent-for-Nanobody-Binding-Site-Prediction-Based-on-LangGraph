from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., dict[str, Any]]
    roles: frozenset[str] = frozenset({"default"})
    outbound: bool = False  # True = may call external network (disabled by default)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_tools(self, role: str = "default") -> list[dict[str, str]]:
        out = []
        for t in self._tools.values():
            if role in t.roles or "default" in t.roles:
                out.append(
                    {
                        "name": t.name,
                        "description": t.description,
                        "outbound": str(t.outbound),
                    }
                )
        return out

    def allowed(self, name: str, role: str) -> bool:
        t = self._tools.get(name)
        if not t:
            return False
        return role in t.roles or "default" in t.roles

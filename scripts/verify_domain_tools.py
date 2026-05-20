# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nanobody_agent.config import get_settings
from nanobody_agent.tools.executor import ToolExecutor, format_tool_answer


def main() -> None:
    s = get_settings()
    ex = ToolExecutor(s)  # 默认使用 settings.tool_actor_role（scientist）
    for q in [
        "噬菌体展示库 PD-L1 KD小于20nM",
        "NB-001 SPR 动力学",
        "PDB 1ABC 链A与链B接触",
        "FoldX 突变扫描 ddG RMSD",
    ]:
        print("Q:", q)
        res = ex.invoke_all(q)
        print(format_tool_answer(res)[:400], "...\n")


if __name__ == "__main__":
    main()

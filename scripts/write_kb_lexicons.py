# -*- coding: utf-8 -*-
"""Write UTF-8 entity_aliases.json and qualitative_map.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "knowledge_base"

ENTITY = {
    "纳米抗体": ["nanobody", "Nanobody", "单域抗体", "VHH抗体", "重链抗体"],
    "VHH": ["重链可变区", "单域抗体可变区", "VHH domain"],
    "结合位点": ["表位", "epitope", "binding site", "抗原结合位点"],
    "NanoKGAT": ["nanoKGAT", "图神经网络结合位点预测"],
    "亲和力": ["binding affinity", "KD", "解离常数"],
}

QUALITATIVE = {
    "显著": "统计显著 (通常 p<0.05) 或效应量较大",
    "明显": "可观测的实质性差异",
    "略微": "小幅度变化",
    "大幅": "效应量或变化幅度较大",
    "轻微": "变化幅度较小",
    "强烈": "结合亲和力高或信号强度大",
    "优于": "实验组相对对照组更优",
    "劣于": "实验组相对对照组更差",
}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "entity_aliases.json").write_bytes(
        json.dumps(ENTITY, ensure_ascii=False, indent=2).encode("utf-8")
    )
    (ROOT / "qualitative_map.json").write_bytes(
        json.dumps(QUALITATIVE, ensure_ascii=False, indent=2).encode("utf-8")
    )
    print("Wrote lexicons to", ROOT)


if __name__ == "__main__":
    main()

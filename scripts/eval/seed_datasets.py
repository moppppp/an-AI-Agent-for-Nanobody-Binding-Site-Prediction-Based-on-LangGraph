#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create default labeled datasets + reference_metrics for pilot study."""
from __future__ import annotations

import json
from pathlib import Path

DATASETS = Path(__file__).resolve().parent / "datasets"


def seed() -> None:
    DATASETS.mkdir(parents=True, exist_ok=True)

    routing = [
        {"query": "什么是纳米抗体", "expected": "kb", "note": "定义"},
        {"query": "纳米抗体与单克隆抗体有什么区别", "expected": "kb", "note": "对比"},
        {"query": "请预测该序列的结合位点 EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAK", "expected": "nanokgat"},
        {"query": "用 PyMOL 可视化纳米抗体三维结构", "expected": "nanokgat"},
        {"query": "今天上海天气怎么样", "expected": "reject"},
        {"query": "比特币最新价格", "expected": "reject"},
        {"query": "图神经网络在抗体结合位点预测中的应用", "expected": "kb"},
        {"query": "AntiBERTy 在纳米抗体研究中的作用", "expected": "kb"},
        {"query": "帮我写一封请假邮件", "expected": "reject"},
        {"query": "结合位点预测常用数据集有哪些", "expected": "kb"},
    ]
    (DATASETS / "routing_labels.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in routing) + "\n", encoding="utf-8"
    )

    retrieval = [
        {"query": "什么是纳米抗体", "needle": "纳米抗体"},
        {"query": "结合位点预测", "needle": "结合"},
        {"query": "图神经网络", "needle": "图神经"},
        {"query": "AntiBERTy", "needle": "AntiBERTy"},
        {"query": "单域抗体 VHH", "needle": "VHH"},
        {"query": "重链可变区", "needle": "可变"},
        {"query": "纳米抗体 定义", "needle": "纳米"},
        {"query": "binding site prediction", "needle": "binding"},
    ]
    (DATASETS / "retrieval_labels.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in retrieval) + "\n", encoding="utf-8"
    )

    halluc = [
        {"query": "今天天气怎么样", "expect_route": "reject", "forbid_in_answer": []},
        {"query": "比特币明天涨还是跌", "expect_route": "reject", "forbid_in_answer": []},
        {"query": "什么是纳米抗体", "expect_route": "kb", "require_citation": True, "needle_in_context": "纳米抗体"},
        {"query": "纳米抗体与单克隆抗体的区别", "expect_route": "kb", "require_citation": True, "needle_in_context": "抗体"},
        {"query": "图神经网络 结合位点", "expect_route": "kb", "require_citation": True, "needle_in_context": "图神经"},
    ]
    (DATASETS / "hallucination_checks.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in halluc) + "\n", encoding="utf-8"
    )

    ref = {
        "meta": {
            "description": "小范围对比测试参考值（简历/论文记录）。run_benchmarks 仅作对照，非自动断言。",
            "participants_approx": "70-80",
            "cohorts": ["实验室同学", "导师", "学院开放日活动访客"],
            "comparison": "端到端大模型 vs Agent+RAG 智能体",
        },
        "routing_accuracy_pct": 88.7,
        "routing_lift_vs_fixed_retrieval_pct": 15.4,
        "hybrid_retrieval_lift_vs_dense_only_pct": 12.9,
        "hallucination_rate_pct": 2.8,
        "pdb_upload_success_rate_pct": 98.3,
        "pdb_test_files_count": 3000,
        "pdf_ingested_count_note": "200+ 篇纳米抗体相关 PDF 自动化清洗与结构化入库",
    }
    (DATASETS / "reference_metrics.json").write_text(
        json.dumps(ref, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    tasks = {
        "study_id": "nanobody_agent_pilot_2025",
        "description": "baseline_e2e（仅端到端大模型） vs agent_rag（本系统）",
        "roles": ["lab_student", "advisor", "teacher", "open_day_visitor"],
        "tasks": [
            {"id": "T1_definition", "title": "概念定义", "instruction": "提问「什么是纳米抗体」，评估准确性与文献可追溯性。", "suggested_duration_min": 3},
            {"id": "T2_comparison", "title": "对比分析", "instruction": "提问纳米抗体与单克隆抗体区别，记录是否胡编、是否有引用。", "suggested_duration_min": 5},
            {"id": "T3_literature", "title": "文献可追溯", "instruction": "提问图神经网络与结合位点预测，检查来源是否可核对（导师关注）。", "suggested_duration_min": 5},
            {"id": "T4_prediction", "title": "结构/位点", "instruction": "上传 PDB 或粘贴序列，请求结合位点预测或 PyMOL 可视化。", "suggested_duration_min": 8},
            {"id": "T5_off_domain", "title": "域外拒答", "instruction": "提问与纳米抗体无关的问题，系统应拒答。", "suggested_duration_min": 2},
        ],
        "subjective_questions": [
            {"id": "Q_traceability", "text": "回答是否有可追溯的文献/知识来源（1-5）"},
            {"id": "Q_time_saved", "text": "是否节省了你的时间（1-5，实验室同学）"},
            {"id": "Q_clarity", "text": "是否让你清楚自己在做什么（1-5，非技术同学）"},
            {"id": "Q_rigor", "text": "学术严谨性（1-5，导师）"},
        ],
    }
    (DATASETS / "user_study_tasks.json").write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Seeded", DATASETS)


if __name__ == "__main__":
    seed()

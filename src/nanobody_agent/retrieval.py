from __future__ import annotations

import re
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from nanobody_agent.config import Settings
from nanobody_agent.kb_enrichment import KnowledgeEnrichment, KnowledgeChunk
from nanobody_agent.llm_utils import classify_intent_rules
from nanobody_agent.semantic_verify import SemanticVerifier
from nanobody_agent.sequence_embed import embed_sequence, is_sequence_query

_DOMAIN_PHRASES = (
    "纳米抗体",
    "单域抗体",
    "重链可变区",
    "vhh",
    "nanobody",
    "nanobodies",
)
_QUESTION_STOP = frozenset(
    "什么 是什么 什么是 如何 为什么 吗 呢 的 了 请 介绍 概念 定义".split()
)


def _read_text_file(path: Path) -> str | None:
    data = path.read_bytes()
    if not data.strip():
        return ""
    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16-le")
    if data.startswith(b"\xfe\xff"):
        return data.decode("utf-16-be")
    if b"\x00" in data[: min(200, len(data))]:
        try:
            return data.decode("utf-16-le")
        except UnicodeDecodeError:
            pass
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+|[\u4e00-\u9fff]", text.lower())


def _routing_query_variants(query: str) -> list[str]:
    q = query.strip()
    variants = [q]
    if "纳米抗体" in q:
        variants.append("纳米抗体 单域抗体 VHH 重链可变区 定义")
    if "结合位点" in q or "表位" in q:
        variants.append(q + " 纳米抗体 结合位点预测")
    return variants


def _content_overlap(query: str, doc: str) -> float:
    doc_l = doc.lower()
    q_l = query.lower()
    phrase_hit = sum(1 for p in _DOMAIN_PHRASES if p in q_l and p in doc_l)
    if phrase_hit:
        return min(1.0, 0.55 + 0.15 * phrase_hit)
    terms = [t for t in _tokenize(query) if t not in _QUESTION_STOP and len(t) >= 2]
    if not terms:
        terms = [t for t in _tokenize(query) if t not in _QUESTION_STOP]
    if not terms:
        return 0.0
    hit = sum(1 for t in terms if t in doc_l)
    return hit / len(terms)


def _minmax_norm(scores: np.ndarray) -> np.ndarray:
    if scores.size == 0:
        return scores
    lo, hi = float(scores.min()), float(scores.max())
    if hi - lo < 1e-12:
        return np.ones_like(scores, dtype=np.float64)
    return (scores - lo) / (hi - lo)


class HybridRetriever:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._chunks: list[KnowledgeChunk] = []
        self._docs: list[str] = []
        self._bm25: BM25Okapi | None = None
        self._index: faiss.Index | None = None
        self._model: SentenceTransformer | None = None
        self._verifier = SemanticVerifier(settings)
        self._enrichment = KnowledgeEnrichment(settings)
        self._seq_doc_emb: np.ndarray | None = None
        self._last_query_enrichment: dict = {}

    def _collect_corpus_paths(self) -> list[Path]:
        root = self.settings.knowledge_dir
        exts = {".md", ".txt", ".json"}
        paths: list[Path] = []
        for p in sorted(root.glob("**/*")):
            if not p.is_file() or p.suffix.lower() not in exts:
                continue
            if not self.settings.knowledge_include_ocr and "ingested_ocr" in p.parts:
                continue
            paths.append(p)
        return paths

    def load_corpus(self, paths: list[Path] | None = None) -> None:
        root = self.settings.knowledge_dir
        if paths is None:
            paths = self._collect_corpus_paths()

        print(f"[nanobody] 扫描知识库: {root} ({len(paths)} 个文件)", flush=True)
        if paths and not self.settings.knowledge_include_ocr:
            print("[nanobody] 已跳过 ingested_ocr/（设 KNOWLEDGE_INCLUDE_OCR=true 可纳入）", flush=True)

        self._chunks = self._enrichment.load_chunks(paths)
        self._docs = [c.aligned_text for c in self._chunks]
        print(
            f"[nanobody] 文本片段: {len(self._docs)} 条 "
            f"(实体对齐/时效元数据已解析)",
            flush=True,
        )
        if not self._docs:
            self._bm25 = None
            self._index = None
            self._model = None
            return

        print("[nanobody] 构建 BM25 索引…", flush=True)
        tokenized = [_tokenize(d) for d in self._docs]
        self._bm25 = BM25Okapi(tokenized)

        emb_name = self.settings.embedding_model
        print(f"[nanobody] 加载向量模型: {emb_name}", flush=True)
        if "minilm" in emb_name.lower():
            print(
                "[nanobody] 警告: MiniLM 对中文相关性偏低，建议在 .env 使用 "
                "EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5 并重启以重建索引",
                flush=True,
            )
        self._model = SentenceTransformer(emb_name)
        n = len(self._docs)
        if n > 50:
            print(f"[nanobody] 正在向量化 {n} 条片段（CPU 可能需 1～10 分钟）…", flush=True)
        embeddings = self._model.encode(
            self._docs,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=n > 30,
            batch_size=64,
        )
        dim = int(embeddings.shape[1])
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(embeddings.astype(np.float32))
        if self.settings.antiberty_enabled:
            self._build_sequence_doc_embeddings()
        print("[nanobody] 知识库索引完成，可以对话。", flush=True)

    def _build_sequence_doc_embeddings(self) -> None:
        """Precompute lightweight sequence embeddings for AA-rich chunks."""
        vecs: list[np.ndarray] = []
        for doc in self._docs:
            letters = "".join(c for c in doc.upper() if c.isalpha())
            if len(letters) >= 20 and sum(1 for c in letters if c in "ACDEFGHIKLMNPQRSTVWY") / len(letters) > 0.35:
                v = embed_sequence(letters[:400])
                vecs.append(v if v is not None else np.zeros(384))
            else:
                vecs.append(np.zeros(384))
        if vecs:
            self._seq_doc_emb = np.stack(vecs, axis=0)

    def _prepare_query(self, query: str) -> str:
        q, meta = self._enrichment.prepare_query(query)
        self._last_query_enrichment = meta
        return q

    def score_breakdown(self, query: str) -> dict[str, float]:
        """Hybrid routing scores; routing_score is used for KB vs LLM gate."""
        query = self._prepare_query(query)
        if not query.strip() or not self._docs or self._bm25 is None or self._index is None or self._model is None:
            return {
                "dense_top": 0.0,
                "bm25_top": 0.0,
                "bm25_part": 0.0,
                "hybrid": 0.0,
                "routing_score": 0.0,
            }

        q_tokens = _tokenize(query)
        bm25_scores = np.array(self._bm25.get_scores(q_tokens), dtype=np.float64)
        bm25_top = float(bm25_scores.max()) if bm25_scores.size else 0.0
        k = float(self.settings.bm25_smooth_k)
        bm25_part = bm25_top / (bm25_top + k) if bm25_top > 0 else 0.0

        dense_top = 0.0
        top_idx = -1
        for qv in _routing_query_variants(query):
            q_emb = self._model.encode(
                [qv],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype(np.float32)
            sims, idxs = self._index.search(q_emb, 1)
            if sims.size and int(idxs[0][0]) >= 0:
                d = max(0.0, min(1.0, float(sims[0][0])))
                if d > dense_top:
                    dense_top = d
                    top_idx = int(idxs[0][0])

        overlap_boost = 0.0
        if top_idx >= 0:
            overlap_boost = _content_overlap(query, self._docs[top_idx])

        w = float(self.settings.hybrid_dense_weight)
        hybrid = w * dense_top + (1.0 - w) * bm25_part
        routing_score = max(hybrid, dense_top * 0.95, bm25_part * 0.88)
        if overlap_boost >= 0.45:
            routing_score = max(routing_score, 0.55 + 0.35 * overlap_boost)
        routing_score = max(0.0, min(1.0, routing_score))
        return {
            "dense_top": dense_top,
            "bm25_top": bm25_top,
            "bm25_part": bm25_part,
            "hybrid": hybrid,
            "overlap_boost": overlap_boost,
            "routing_score": routing_score,
            "query_enrichment": dict(self._last_query_enrichment),
        }

    def max_relevance(self, query: str) -> float:
        return self.score_breakdown(query)["routing_score"]

    def _top_passage_for_verify(self, query: str) -> str:
        hits = self.retrieve(query, top_k=1)
        if hits:
            return hits[0]["text"]
        return ""

    def semantic_verify(self, query: str) -> float:
        passage = self._top_passage_for_verify(query)
        if not passage:
            return 0.0
        if self._verifier.model_name == self.settings.embedding_model and self._model is not None:
            emb = self._model.encode(
                [query, passage],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return float(np.clip(np.dot(emb[0], emb[1]), 0.0, 1.0))
        return self._verifier.similarity(query, passage)

    def decide_kb_route(self, query: str) -> dict:
        """
        KB routing:
        - routing_score >= gray_high -> KB
        - [threshold, gray_high) -> secondary semantic verify
        - [verify_low, threshold) -> extended gray verify
        - definition + domain overlap + semantic pass -> KB rescue
        """
        low = float(self.settings.kb_relevance_threshold)
        high = float(self.settings.kb_relevance_gray_high)
        verify_low = float(self.settings.kb_relevance_verify_low)
        thresh = float(self.settings.semantic_verify_threshold)

        bd = self.score_breakdown(query)
        rel = float(bd["routing_score"])
        reject_thr = float(self.settings.kb_reject_threshold)
        out: dict = {
            "relevance": rel,
            "relevance_detail": bd,
            "semantic_verify_score": None,
            "route_kb": False,
            "gray_zone": False,
            "reject": False,
            "extended_retrieval": False,
        }

        def _apply_verify() -> None:
            sem = self.semantic_verify(query)
            out["semantic_verify_score"] = sem
            out["route_kb"] = sem >= thresh

        if rel >= high:
            out["route_kb"] = True
            return out

        if rel >= low:
            out["gray_zone"] = True
            _apply_verify()
            if out["route_kb"]:
                out["relevance"] = max(rel, low + 0.001)
            return out

        if rel >= verify_low:
            out["gray_zone"] = True
            _apply_verify()
            if out["route_kb"]:
                out["relevance"] = max(rel, low + 0.001)
            return out

        _apply_verify()
        overlap = float(bd.get("overlap_boost") or 0.0)
        intent = classify_intent_rules(query)
        sem = float(out["semantic_verify_score"] or 0.0)
        if intent == "definition" and overlap >= 0.45 and sem >= thresh - 0.06:
            out["route_kb"] = True
            out["relevance"] = max(rel, low + 0.001)
            return out
        if sem >= thresh and (
            bd["bm25_part"] >= 0.22 or bd["dense_top"] >= 0.28 or overlap >= 0.4
        ):
            out["route_kb"] = True
            out["relevance"] = max(rel, verify_low + 0.01)
            return out

        if rel < reject_thr and sem < thresh - 0.05:
            out["reject"] = True
        elif rel < low:
            out["extended_retrieval"] = True
        return out

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        if not query.strip():
            return []
        if not self._docs or self._bm25 is None or self._index is None or self._model is None:
            return []

        query = self._prepare_query(query)
        q_tokens = _tokenize(query)
        bm25_scores = np.array(self._bm25.get_scores(q_tokens), dtype=np.float64)
        bm25_n = _minmax_norm(bm25_scores)

        q_emb = self._model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype(np.float32)
        dense_scores = np.zeros(len(self._docs), dtype=np.float64)
        sims, idxs = self._index.search(q_emb, min(top_k * 3, len(self._docs)))
        for j, i in enumerate(idxs[0]):
            if i < 0:
                continue
            dense_scores[int(i)] = float(sims[0][j])
        dense_n = _minmax_norm(dense_scores)

        w = float(self.settings.hybrid_dense_weight)
        hybrid = w * dense_n + (1.0 - w) * bm25_n

        for i, ch in enumerate(self._chunks):
            hybrid[i] *= self._enrichment.temporal_weight(ch.year)

        if self.settings.fact_drift_enabled and self._chunks:
            hybrid_list = hybrid.tolist()
            hybrid_list, drift_events = self._enrichment.apply_fact_drift(
                hybrid_list, self._chunks
            )
            hybrid = np.array(hybrid_list, dtype=np.float64)
            if drift_events:
                self._last_query_enrichment["fact_drift"] = drift_events[:5]

        if is_sequence_query(query) and self._seq_doc_emb is not None:
            from nanobody_agent.sequence_embed import extract_sequence

            seq = extract_sequence(query)
            if seq:
                qv = embed_sequence(seq)
                if qv is not None:
                    sims = self._seq_doc_emb @ qv
                    boost = float(self.settings.sequence_dense_boost)
                    hybrid = np.clip(hybrid + boost * sims, 0.0, 1.0)

        order = np.argsort(-hybrid)[:top_k]

        out: list[dict] = []
        for rank, i in enumerate(order):
            i = int(i)
            score = float(hybrid[i])
            ch = self._chunks[i]
            out.append(
                {
                    "rank": rank + 1,
                    "score": score,
                    "text": ch.text,
                    "source": ch.source,
                    "year": ch.year,
                    "temporal_weight": self._enrichment.temporal_weight(ch.year),
                }
            )
        return out

    def retrieve_extended(self, query: str, top_k: int | None = None) -> list[dict]:
        """Second-pass retrieval with query variants for low-relevance cases."""
        k = top_k or int(self.settings.kb_extended_retrieval_top_k)
        seen: set[str] = set()
        merged: list[dict] = []
        for qv in _routing_query_variants(query):
            for h in self.retrieve(qv, top_k=max(3, k // 2)):
                key = h["text"][:120]
                if key in seen:
                    continue
                seen.add(key)
                merged.append(h)
        merged.sort(key=lambda x: -float(x.get("score") or 0))
        for i, h in enumerate(merged[:k], start=1):
            h["rank"] = i
        return merged[:k]

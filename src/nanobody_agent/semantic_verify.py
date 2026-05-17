from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from nanobody_agent.config import Settings


class SemanticVerifier:
    """Lightweight local embedding model for gray-zone semantic re-check."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: SentenceTransformer | None = None

    @property
    def model_name(self) -> str:
        name = (self.settings.semantic_verify_model or "").strip()
        return name or self.settings.embedding_model

    def get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def similarity(self, query: str, passage: str) -> float:
        if not query.strip() or not passage.strip():
            return 0.0
        model = self.get_model()
        emb = model.encode(
            [query, passage],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return float(np.clip(np.dot(emb[0], emb[1]), 0.0, 1.0))

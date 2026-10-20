"""Match a student question to the most relevant learning objective.

The matcher uses a small sentence embedding model with ONNX Runtime
(fastembed), so it does not need PyTorch or a GPU. If the model is not
available, it uses fuzzy text matching (rapidfuzz).

Environment variables:

``EMBEDDING_MODEL``
    The fastembed model name. Default: sentence-transformers/all-MiniLM-L6-v2.
``EMBEDDING_CACHE_DIR``
    The directory of the model files. The Docker image downloads the model
    to this directory at build time.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("jelai.lo_matcher")

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def embedding_settings() -> Tuple[str, Optional[str]]:
    return (
        os.getenv("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL,
        os.getenv("EMBEDDING_CACHE_DIR") or None,
    )


class LearningObjectiveMatcher:
    def __init__(self):
        self.model = None
        self._cache: Dict[tuple, object] = {}

    def load(self):
        """Load the embedding model. On failure, the fuzzy matcher is used."""
        model_name, cache_dir = embedding_settings()
        try:
            from fastembed import TextEmbedding
            self.model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)
            logger.info("Embedding model %s loaded.", model_name)
        except Exception as e:
            logger.warning("Embedding model %s is not available (%s). Fuzzy matching is used.", model_name, e)
            self.model = None

    def _embed(self, texts: List[str]):
        import numpy as np
        vectors = np.array(list(self.model.embed(texts)), dtype="float32")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    def scores(self, question: str, objectives: List[str]) -> List[float]:
        """Return a similarity from 0 to 1 for each objective."""
        if self.model is not None:
            try:
                key = tuple(objectives)
                if key not in self._cache:
                    self._cache[key] = self._embed(list(key))
                question_vector = self._embed([question])[0]
                return [float(v) for v in self._cache[key] @ question_vector]
            except Exception as e:
                logger.error("Embedding similarity failed (%s). Fuzzy matching is used.", e)
        from rapidfuzz import fuzz
        return [fuzz.token_set_ratio(question, objective) / 100.0 for objective in objectives]

    def best_match(self, question: str, objectives: List[str]) -> Tuple[Optional[str], float]:
        """Return the best objective and its score, or (None, 0.0) if there are none."""
        if not objectives:
            return None, 0.0
        values = self.scores(question, objectives)
        index = max(range(len(values)), key=values.__getitem__)
        return objectives[index], values[index]


def download_model():
    """Download the embedding model to EMBEDDING_CACHE_DIR (used at image build time)."""
    from fastembed import TextEmbedding
    model_name, cache_dir = embedding_settings()
    model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)
    list(model.embed(["warm up"]))
    print(f"Downloaded {model_name} to {cache_dir or 'the default cache'}")


if __name__ == "__main__":
    download_model()

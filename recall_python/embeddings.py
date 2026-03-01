import sys
import numpy as np


class EmbeddingService:
    EMBEDDING_DIM = 384

    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.is_available = False
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
            self.is_available = True
            print(f"Embedding model loaded: {model_name}", file=sys.stderr)
        except Exception as e:
            print(f"Embedding model not available: {e}", file=sys.stderr)
            print("Vector search disabled, falling back to text search.", file=sys.stderr)

    def embed(self, text):
        if not self.is_available:
            raise RuntimeError("Embedding model not available")
        return self._model.encode(text, normalize_embeddings=True)

    @staticmethod
    def similarity(a, b):
        return float(np.dot(a, b))

    @staticmethod
    def serialize(embedding):
        return np.array(embedding, dtype=np.float32).tobytes()

    @staticmethod
    def deserialize(blob):
        return np.frombuffer(blob, dtype=np.float32)

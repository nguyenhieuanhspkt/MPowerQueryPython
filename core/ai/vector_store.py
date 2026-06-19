import faiss
import numpy as np


class VectorStore:
    """Lightweight in-memory FAISS index — built on-the-fly from current DataFrame column."""

    def __init__(self):
        self.index = None
        self.metadata = []

    def build_index(self, vectors: np.ndarray, metadata: list):
        """
        vectors : np.ndarray shape (N, D)
        metadata: list of dicts — one per row, stored alongside the index
        """
        dim = vectors.shape[1]
        self.metadata = metadata
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors_norm = (vectors / (norms + 1e-12)).astype(np.float32)
        self.index = faiss.IndexFlatIP(dim)   # cosine via inner product on unit vectors
        self.index.add(vectors_norm)

    def search(self, query_vec: np.ndarray, top_k: int = 50):
        """
        Returns list of {'score', 'row_index', 'metadata'} sorted by score desc.
        """
        if self.index is None:
            raise RuntimeError("Index chưa được build.")
        q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-12)
        q = q_norm.reshape(1, -1).astype(np.float32)
        top_k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(q, top_k)
        return [
            {"score": float(s), "row_index": int(i), "metadata": self.metadata[i]}
            for s, i in zip(scores[0], indices[0])
            if i != -1
        ]

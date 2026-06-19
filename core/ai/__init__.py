_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        from core.ai.embedder import DataEmbedder
        _embedder = DataEmbedder()
    return _embedder

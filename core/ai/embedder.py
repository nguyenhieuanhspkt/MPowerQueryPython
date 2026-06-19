import torch
import numpy as np
from sentence_transformers import SentenceTransformer

BGE_MODEL_PATH = r"D:\TaskApp_kiet\TaskApp\search_item2\search_item\back_end\AI_models\BGE"


class DataEmbedder:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[BGE] Đang nạp model từ: {BGE_MODEL_PATH}")
        self.model = SentenceTransformer(BGE_MODEL_PATH, device=self.device)
        print(f"[BGE] Model sẵn sàng trên {self.device.upper()}")

    def embed_documents(self, texts, batch_size=16, show_progress=False):
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return embeddings

    def embed_query(self, query):
        return self.model.encode([query], convert_to_numpy=True)[0]

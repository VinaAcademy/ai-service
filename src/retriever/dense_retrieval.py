import os

import faiss
import numpy as np
from langchain_openai import OpenAIEmbeddings


class DenseRetriever:
    def __init__(
        self,
        passages,
        embedding_model: str = "text-embedding-3-small",
        index_path: str = "./data/faiss.index",
        embed_path: str = "./data/embeddings.npy",
            openai_api_key: str = None,
    ):
        """
        passages: list of dict {"content": ...}
        embedding_model: OpenAI embedding model
        """
        self.passages = passages
        self.texts = [p["content"] for p in passages]
        self.embedding_model = embedding_model
        self.index_path = index_path
        self.embed_path = embed_path
        self.openai_api_key = openai_api_key
        self.index = None
        self.embeddings = None
        self.embedder = OpenAIEmbeddings(
            model=self.embedding_model, api_key=self.openai_api_key
        )

    def build_index(self):
        if os.path.exists(self.index_path) and os.path.exists(self.embed_path):
            print("🔄 Loading precomputed embeddings & FAISS index...")
            self.embeddings = np.load(self.embed_path)
            d = self.embeddings.shape[1]
            self.index = faiss.read_index(self.index_path)
        else:
            print("⚡ Computing embeddings via OpenAI...")
            self.embeddings = np.array(
                [self.embedder.embed_query(text) for text in self.texts],
                dtype="float32",
            )
            np.save(self.embed_path, self.embeddings)
            d = self.embeddings.shape[1]
            self.index = faiss.IndexFlatIP(d)
            self.index.add(self.embeddings)
            faiss.write_index(self.index, self.index_path)

    def search(self, query: str, top_k: int = 5):
        if self.index is None:
            self.build_index()
        q_emb = np.array([self.embedder.embed_query(query)], dtype="float32")
        D, indices = self.index.search(q_emb, min(top_k, len(self.texts)))
        results = []
        for rank, idx in enumerate(indices[0]):
            if 0 <= idx < len(self.texts):  # Ensure index is valid
                results.append((idx, self.texts[idx], float(D[0][rank])))
        return results

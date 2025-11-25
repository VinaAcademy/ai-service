class RRFFusion:
    def __init__(self, bm25, dense, rrf_k: int = 60):
        self.bm25 = bm25
        self.dense = dense
        self.rrf_k = rrf_k

    def fuse(self, query: str, top_k: int = 10):
        bm25_results = self.bm25.search(query, top_k)
        dense_results = self.dense.search(query, top_k)

        scores = {}
        for rank, (idx, _, _) in enumerate([r for r in bm25_results]):
            scores[idx] = scores.get(idx, 0) + 1 / (self.rrf_k + rank + 1)

        for rank, (idx, _, _) in enumerate([r for r in dense_results]):
            scores[idx] = scores.get(idx, 0) + 1 / (self.rrf_k + rank + 1)

        reranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [(idx, self.bm25.texts[idx]) for idx, _ in reranked]

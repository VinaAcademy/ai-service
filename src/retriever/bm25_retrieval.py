from rank_bm25 import BM25Okapi


def simple_tokenize(text: str):
    return [t.strip() for t in text.lower().split() if t.strip()]


class BM25Retriever:
    def __init__(self, passages):
        self.texts = [p["content"] for p in passages]
        self.tokenized = [simple_tokenize(t) for t in self.texts]
        self.model = BM25Okapi(self.tokenized)

    def search(self, query: str, top_k: int = 5):
        tokenized_query = simple_tokenize(query)
        scores = self.model.get_scores(tokenized_query)
        top_idx = scores.argsort()[::-1][:top_k]
        return [(idx, self.texts[idx], scores[idx]) for idx in top_idx]

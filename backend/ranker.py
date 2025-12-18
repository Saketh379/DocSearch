# backend/ranker.py
import math
from collections import Counter

class Ranker:

    def __init__(self, indexer):
        self.indexer = indexer

    def _idf(self, term):
        df = self.indexer.doc_freq.get(term, 0)
        N = self.indexer.doc_count if self.indexer.doc_count > 0 else 1
        return math.log((N + 1) / (df + 1)) + 1.0

    def rank(self, query_tokens, top_k=5):
        q_tf = Counter(query_tokens)
        q_vec = {}
        for t, cnt in q_tf.items():
            q_vec[t] = cnt * self._idf(t)
        q_len = math.sqrt(sum(v * v for v in q_vec.values()))
        scores = {}
        for term, q_w in q_vec.items():
            postings = self.indexer.lookup(term)
            idf = self._idf(term)
            for doc_id, tf in postings.items():
                d_w = tf * idf
                scores.setdefault(doc_id, 0.0)
                scores[doc_id] += q_w * d_w
        for doc_id in list(scores.keys()):
            d_len = float(self.indexer.doc_lengths.get(doc_id, 1.0))
            denom = q_len * d_len
            if denom > 0:
                scores[doc_id] = scores[doc_id] / denom
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

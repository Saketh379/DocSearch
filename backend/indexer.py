# backend/indexer.py
import os
import json
from collections import defaultdict, Counter

class Indexer:

    def __init__(self, index_path="index.json"):
        self.index_path = index_path
        self.index = defaultdict(dict)
        self.doc_count = 0
        self.doc_freq = {}
        self.doc_lengths = {}
        if os.path.exists(index_path):
            self._load()

    def _load(self):
        with open(self.index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.index = defaultdict(dict, {term: term_info for term, term_info in data.get("index", {}).items()})
        self.doc_count = data.get("doc_count", 0)
        self.doc_freq = data.get("doc_freq", {})
        self.doc_lengths = data.get("doc_lengths", {})

    def _save(self):
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump({
                "index": dict(self.index), 
                "doc_count": self.doc_count, 
                "doc_freq": self.doc_freq, 
                "doc_lengths": self.doc_lengths
                }, f, indent=4)

    def index_document(self, doc_id, tokens):
        if str(doc_id) in self.doc_lengths:
            return
        freq = Counter(tokens)
        for term, f in freq.items():
            self.index[term][str(doc_id)] = f
            self.doc_freq[term] = self.doc_freq.get(term, 0) + 1
        self.doc_count += 1
        self.doc_lengths[str(doc_id)] = sum(f ** 2 for f in freq.values()) ** 0.5
        self._save()

    def remove_index(self, doc_id):
        if str(doc_id) not in self.doc_lengths:
            return
        del self.doc_lengths[str(doc_id)]
        self.doc_count -= 1
        terms_to_del = []
        for term in self.index.keys():
            postings = self.index[term]
            if str(doc_id) in postings:
                del postings[str(doc_id)]
                if term in self.doc_freq:
                    self.doc_freq[term] -= 1
                    if self.doc_freq[term] <= 0:
                        del self.doc_freq[term]
                if not postings:
                    terms_to_del.append(term)
        for term in terms_to_del:
            del self.index[term]
        self._save()

    def lookup(self, term):
        return self.index.get(term, {})

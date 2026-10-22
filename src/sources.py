"""Search over public documents: full-text passages (openly licensed documents only) and fact
cards (our own statements of figures from the others). See config/sources.py.

Passages are embedded with a small CPU model through fastembed (ONNX Runtime, no PyTorch).
A question is embedded the same way, and the closest passages by cosine similarity come back.
Retrieval only finds text; Python tools still do all the arithmetic.
"""

import json
import os
import re
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_DIR = PROJECT_ROOT / os.environ.get("MODEL_DIR", "data/models")
INDEX_FILE = PROJECT_ROOT / os.environ.get("SOURCES_INDEX", "data/index/sources.json")
PASSAGE_WORDS = 250  # bge-small reads at most 512 tokens (~380 words); 500 would be cut off
OVERLAP_WORDS = 50
MAX_K = 10

# Some PDFs extract unmapped glyphs as "/gid00030"-style tokens; they carry no meaning.
_GLYPH_TOKEN = re.compile(r"/gid\d+")


def page_words(pdf_path):
    """[(page_number, word), ...] for every word in the PDF, in reading order."""
    from pypdf import PdfReader  # only needed when building the index

    words = []
    for number, page in enumerate(PdfReader(pdf_path).pages, start=1):
        text = _GLYPH_TOKEN.sub(" ", page.extract_text() or "")
        words += [(number, word) for word in text.split()]
    return words


def split_passages(words, size=PASSAGE_WORDS, overlap=OVERLAP_WORDS):
    """Split [(page, word)] into passages of `size` words, each overlapping the last by
    `overlap` words, so a figure near a boundary appears whole in at least one passage.
    Returns [{"text", "page", "pages"}]: page is where the passage starts."""
    passages = []
    step = size - overlap
    for start in range(0, max(len(words), 1), step):
        chunk = words[start:start + size]
        if not chunk:
            break
        first, last = chunk[0][0], chunk[-1][0]
        passages.append({
            "text": " ".join(word for _, word in chunk),
            "page": first,
            "pages": str(first) if first == last else f"{first}-{last}",
        })
        if start + size >= len(words):
            break
    return passages


_model = None


def embedder():
    """The embedding model, loaded once (it is downloaded to MODEL_DIR the first time)."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(MODEL_DIR))
    return _model


def _unit(vectors):
    vectors = np.asarray(vectors, dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=-1, keepdims=True)


def embed_passages(texts):
    return _unit(list(embedder().passage_embed(texts)))


def embed_query(text):
    return _unit(next(iter(embedder().query_embed(text))))


_index_cache = {}


def load_index(path=INDEX_FILE):
    """The committed index, cached until the file changes; None if it doesn't exist."""
    path = Path(path)
    if not path.exists():
        return None
    modified = path.stat().st_mtime_ns
    cached = _index_cache.get(str(path))
    if cached is None or cached[0] != modified:
        index = json.loads(path.read_text(encoding="utf-8"))
        index["matrix"] = _unit([p["vector"] for p in index["passages"]])
        _index_cache[str(path)] = (modified, index)
    return _index_cache[str(path)][1]


def search(query, k=5, index=None):
    """The k passages closest to the query, best first, with their source details."""
    index = index if index is not None else load_index()
    if index is None:
        raise FileNotFoundError("No sources index; build it with scripts/build_source_index.py")
    k = max(1, min(int(k), MAX_K))
    scores = index["matrix"] @ embed_query(query)
    documents = {d["id"]: d for d in index["stamp"]["documents"]}
    results = []
    for rank, i in enumerate(np.argsort(-scores)[:k], start=1):
        passage = index["passages"][int(i)]
        doc = documents[passage["doc"]]
        results.append({
            "rank": rank,
            "score": round(float(scores[i]), 3),
            "id": passage["id"],
            "kind": passage["kind"],
            "text": passage["text"],
            "title": doc["title"],
            "publisher": doc["publisher"],
            "date": doc["date"],
            "pages": passage["pages"],
            "url": doc["url"],
        })
    return results

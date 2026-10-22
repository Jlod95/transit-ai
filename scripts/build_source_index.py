"""Build data/index/sources.json from the documents listed in config/sources.py.

Usage:
    python scripts/build_source_index.py

Reads the PDFs in data/raw/sources/ (not committed). Openly licensed documents are split into
~250-word passages with 50 words of overlap (the embedding model reads at most ~380 words);
the others contribute only their fact cards.
Everything is embedded with a small CPU model, and the file is stamped with each document's
SHA-256, the model name and the git commit.
"""

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))  # so "src" and "config" can be imported

from config.sources import DOCUMENTS, FACT_CARDS
from src.provenance import current_git_commit
from src.sources import (
    INDEX_FILE,
    MODEL_NAME,
    OVERLAP_WORDS,
    PASSAGE_WORDS,
    embed_passages,
    page_words,
    split_passages,
)
from src.summaries import file_sha256

SOURCE_DIR = PROJECT_ROOT / "data" / "raw" / "sources"


def build():
    started = time.perf_counter()
    commit = current_git_commit()
    passages, documents = [], []
    for doc in DOCUMENTS:
        path = SOURCE_DIR / doc["file"]
        words = page_words(path)
        page_count = words[-1][0] if words else 0
        if doc["use"] == "full_text":
            found = [
                {"kind": "passage", "text": p["text"], "page": p["page"], "pages": p["pages"]}
                for p in split_passages(words)
            ]
        else:
            cards = [(page, text) for doc_id, page, text in FACT_CARDS if doc_id == doc["id"]]
            if not cards:
                raise ValueError(f"{doc['id']} is facts_only but has no fact cards")
            for page, _ in cards:
                if not 1 <= page <= page_count:
                    raise ValueError(f"{doc['id']}: fact card cites page {page} of {page_count}")
            found = [{"kind": "fact card", "text": t, "page": p, "pages": str(p)} for p, t in cards]
        for n, p in enumerate(found, start=1):
            passages.append({"id": f"{doc['id']}#{n}", "doc": doc["id"], **p})
        documents.append({**doc, "sha256": file_sha256(path), "pages": page_count,
                          "passages": len(found)})
        print(f"  {doc['id']}: {len(found)} {found[0]['kind']}s from {page_count} pages")

    vectors = embed_passages([p["text"] for p in passages])
    for p, v in zip(passages, vectors):
        p["vector"] = [round(float(x), 5) for x in v]

    index = {
        "stamp": {
            "documents": documents,
            "model": MODEL_NAME,
            "dimensions": len(passages[0]["vector"]),
            "passage_words": PASSAGE_WORDS,
            "overlap_words": OVERLAP_WORDS,
            "built_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git_commit": commit,
        },
        "passages": passages,
    }
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {INDEX_FILE} ({INDEX_FILE.stat().st_size / 1000:.0f} kB): {len(passages)} passages "
          f"from {len(documents)} documents in {time.perf_counter() - started:.1f}s; git {commit}")


if __name__ == "__main__":
    build()

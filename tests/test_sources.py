"""The public-sources index: splitting, the committed file and its stamp, licence safety, and
search. Search tests embed the query, so they download the small model on first run."""

from pathlib import Path

import pytest

from config.sources import DOCUMENTS
from scripts.check_retrieval import QUESTIONS, is_right
from src.sources import MODEL_NAME, load_index, search, split_passages

INDEX = Path(__file__).parent.parent / "data" / "index" / "sources.json"


def test_split_passages_overlap_and_pages():
    # 600 words: the first 300 on page 1, the rest on page 2. Passages of 250 words overlapping
    # by 50 start every 200 words: at words 0, 200 and 400.
    words = [(1 if i < 300 else 2, f"w{i}") for i in range(600)]
    passages = split_passages(words, size=250, overlap=50)
    assert [p["text"].split()[0] for p in passages] == ["w0", "w200", "w400"]
    assert [len(p["text"].split()) for p in passages] == [250, 250, 200]
    assert [p["pages"] for p in passages] == ["1", "1-2", "2"]
    # Each passage repeats the last 50 words of the one before.
    assert passages[1]["text"].split()[:50] == passages[0]["text"].split()[-50:]


@pytest.fixture(scope="module")
def index():
    loaded = load_index(INDEX)
    assert loaded is not None, "data/index/sources.json is missing; run scripts/build_source_index.py"
    return loaded


def test_stamp_is_complete(index):
    stamp = index["stamp"]
    assert stamp["model"] == MODEL_NAME
    assert stamp["dimensions"] == 384
    assert [d["id"] for d in stamp["documents"]] == [d["id"] for d in DOCUMENTS]
    for doc in stamp["documents"]:
        assert len(doc["sha256"]) == 64 and doc["url"] and doc["licence"] and doc["passages"] > 0
    assert stamp["git_commit"] != "unknown" and not stamp["git_commit"].endswith("-dirty")


def test_only_openly_licensed_documents_contribute_copied_text(index):
    use = {d["id"]: d["use"] for d in index["stamp"]["documents"]}
    for passage in index["passages"]:
        expected = "passage" if use[passage["doc"]] == "full_text" else "fact card"
        assert passage["kind"] == expected, passage["id"]
    full_text = [d for d in index["stamp"]["documents"] if d["use"] == "full_text"]
    assert all("CC BY" in d["licence"] for d in full_text)


def test_known_query_finds_known_passage(index):
    results = search("How many kilograms of CO2 does a litre of diesel release?", k=3, index=index)
    assert results[0]["id"] == "nrcan_fuel_co2_factsheet#1"
    assert "2.66 kg" in results[0]["text"]
    assert results[0]["url"].startswith("https://www.nrcan.gc.ca/")
    assert results[0]["pages"] == "2"


def test_retrieval_check_recall_at_5(index):
    hits = [
        any(is_right(r, doc_id, phrase) for r in search(question, k=5, index=index))
        for question, doc_id, phrase in QUESTIONS
    ]
    assert sum(hits) / len(hits) >= 0.8, hits

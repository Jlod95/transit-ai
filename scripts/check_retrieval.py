"""Retrieval check: does search_sources find the passage we know answers each question?

Usage:
    python scripts/check_retrieval.py

Each question names the document it should come from and a phrase only the right passage
contains. Reports recall@5: the share of questions whose right passage is in the top 5.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # so "src" can be imported

from src.sources import search

# (question, document id, phrase the right passage contains)
QUESTIONS = [
    ("How much more energy do electric buses use per km in winter than in summer?",
     "vtt_winter_2022", "40–45%"),
    ("What was the total price of Halifax's contract for 60 battery-electric buses and chargers?",
     "halifax_beb_contract_2022", "94,739,857"),
    ("How many kilograms of CO2 does burning one litre of diesel produce?",
     "nrcan_fuel_co2_factsheet", "2.66 kg"),
    ("How much does a depot charger for an electric bus cost to buy and install?",
     "nrel_beb_financial_2020", "$50,000"),
    ("By what year will London's bus fleet be fully zero-emission?",
     "tfl_bus_action_plan_2022", "2034"),
]


def is_right(result, doc_id, phrase):
    return result["id"].startswith(doc_id + "#") and phrase in result["text"]


def recall_at(k=5):
    hits = []
    for question, doc_id, phrase in QUESTIONS:
        results = search(question, k=k)
        rank = next((r["rank"] for r in results if is_right(r, doc_id, phrase)), None)
        hits.append(rank is not None)
        found = f"rank {rank}" if rank else "NOT in top 5"
        print(f"  {found:>14} | {question}\n                 top: {results[0]['id']} ({results[0]['score']})")
    return sum(hits) / len(hits)


if __name__ == "__main__":
    print(f"recall@5 = {recall_at(5):.0%}")

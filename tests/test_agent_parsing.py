import json
from pathlib import Path
import pytest
from backend.agent.agent import regex_fallback_parser

QUERIES_FILE = Path(__file__).parent / "queries.json"

def test_queries_dataset_parsing_accuracy():
    assert QUERIES_FILE.exists()
    queries = json.loads(QUERIES_FILE.read_text(encoding="utf-8"))
    assert len(queries) >= 30

    correct_mode = 0
    correct_entities = 0
    total = len(queries)
    failures = []

    for item in queries:
        text = item["text"]
        expected = item["expected"]
        parsed = regex_fallback_parser(text)

        # Check mode
        mode_match = (parsed["mode"] == expected["mode"])
        if mode_match:
            correct_mode += 1

        # Check origin & destination substring matches (case-insensitive)
        orig_match = (expected["origin"].lower() in parsed["origin"].lower() or parsed["origin"].lower() in expected["origin"].lower())
        dest_match = (expected["destination"].lower() in parsed["destination"].lower() or parsed["destination"].lower() in expected["destination"].lower())

        if orig_match and dest_match:
            correct_entities += 1
        else:
            failures.append({
                "id": item["id"],
                "text": text,
                "expected": expected,
                "got": parsed
            })

    mode_accuracy = (correct_mode / total) * 100.0
    entity_accuracy = (correct_entities / total) * 100.0

    print(f"\n--- Deterministic Parser Evaluation on {total} Diverse Queries ---")
    print(f"Mode Accuracy: {mode_accuracy:.1f}% ({correct_mode}/{total})")
    print(f"Entity (Origin & Destination) Accuracy: {entity_accuracy:.1f}% ({correct_entities}/{total})")
    if failures:
        print(f"Failures ({len(failures)}):")
        for f in failures[:3]:
            print(f"  Query {f['id']}: '{f['text']}' -> Expected: {f['expected']}, Got: {f['got']}")

    # Mode accuracy must be at least 90%, Entity accuracy at least 80%
    assert mode_accuracy >= 90.0
    assert entity_accuracy >= 80.0

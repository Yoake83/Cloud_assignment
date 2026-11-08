import json

import clean


def rec(i, text, raw):
    return {"id": f"C{i:04d}", "text": text, "teacher_raw": raw}


GOOD = json.dumps({"intent": "weather_query", "date": None, "time": None, "place": "london"})


def test_each_rejection_reason_and_counts_add_up():
    records = [
        rec(1, "what is the weather in london", GOOD),                       # kept
        rec(2, "hello", "not json at all"),                                  # a
        rec(3, "hello", json.dumps({"intent": "alarm_set"})),                # b (missing keys)
        rec(4, "hello", json.dumps({"intent": "play_music", "date": None, "time": None, "place": None})),  # c
        rec(5, "what is the weather in london", json.dumps(
            {"intent": "weather_query", "date": None, "time": None, "place": "paris"})),   # d (paris not in text)
        rec(6, "what is the weather in london", GOOD),                       # duplicate of C0001
        rec(7, "set alarm seven am", json.dumps(
            {"intent": "alarm_set", "date": None, "time": "seven am", "place": None})),    # kept
    ]
    kept, counts = clean.clean(records)
    assert counts == {"input": 7, "a": 1, "b": 1, "c": 1, "d": 1, "duplicates": 1, "kept": 2}
    assert [r["id"] for r in kept] == ["C0001", "C0007"]


def test_duplicate_keeps_smallest_id_and_output_is_id_ordered():
    records = [rec(9, "same", json.dumps({"intent": "alarm_query", "date": None, "time": None, "place": None})),
               rec(2, "same", json.dumps({"intent": "alarm_query", "date": None, "time": None, "place": None}))]
    kept, counts = clean.clean(records)
    assert [r["id"] for r in kept] == ["C0002"] and counts["duplicates"] == 1


def test_serialisation_is_deterministic():
    kept, _ = clean.clean([rec(1, "what is the weather in london", GOOD)])
    assert clean.serialise(kept) == clean.serialise(kept)


def test_coverage_detects_gaps_and_repeats():
    missing, repeated = clean.coverage(["A", "B", "C"], [{"id": "A"}, {"id": "A"}, {"id": "B"}])
    assert missing == ["C"] and repeated == ["A"]


def test_empty_string_slot_is_rejected():
    raw = json.dumps({"intent": "weather_query", "date": "", "time": None, "place": None})
    assert clean.reject_reason(rec(1, "weather", raw)) == "d"

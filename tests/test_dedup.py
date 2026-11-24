from expense_tracker.ingest.dedup import make_dedup_key


def test_dedup_stable():
    a = make_dedup_key("Chase", "2026-01-01", -12.34, "STARBUCKS")
    b = make_dedup_key("Chase", "2026-01-01", -12.34, "starbucks")
    assert a == b

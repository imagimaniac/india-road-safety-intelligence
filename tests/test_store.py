import pytest

from india_road_safety.store import Store


def make_store(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.migrate() == 2
    return s


def test_migrate_and_schema_version(tmp_path):
    s = make_store(tmp_path)
    assert s.schema_version() == 2
    s.migrate()  # idempotent
    assert s.schema_version() == 2


def test_insert_accident_record(tmp_path):
    s = make_store(tmp_path)
    rid = s.insert("accident_records", {
        "geography": "India", "geo_level": "national", "year": 2023,
        "month": 6, "severity": "fatal", "metric": "fatalities",
        "value": 100, "source_slug": "morth", "evidence_class": "observed_fact",
        "confidence": "high", "content_hash": "abc",
    })
    assert rid == 1
    assert s.count("accident_records") == 1
    row = s.query("SELECT * FROM accident_records WHERE id=?", (rid,))[0]
    assert row["value"] == 100
    assert row["created_at"]  # auto-populated


def test_insert_none_value_preserved(tmp_path):
    s = make_store(tmp_path)
    rid = s.insert("accident_records", {
        "geography": "India", "geo_level": "national", "year": 2022,
        "severity": "unknown", "metric": "injuries", "value": None,
        "source_slug": "morth", "evidence_class": "observed_fact",
        "confidence": "unverified",
    })
    row = s.query("SELECT value FROM accident_records WHERE id=?", (rid,))[0]
    assert row["value"] is None  # never coerced to 0


def test_insert_rejects_unknown_table(tmp_path):
    s = make_store(tmp_path)
    with pytest.raises(ValueError):
        s.insert("not_a_table", {"x": 1})


def test_insert_rejects_all_invalid_columns(tmp_path):
    s = make_store(tmp_path)
    with pytest.raises(ValueError):
        s.insert("accident_records", {"bogus": 1, "other": 2})


def test_insert_filters_unknown_columns(tmp_path):
    s = make_store(tmp_path)
    rid = s.insert("accident_records", {
        "geography": "India", "geo_level": "national", "year": 2023,
        "severity": "fatal", "metric": "accidents", "source_slug": "morth",
        "evidence_class": "observed_fact", "confidence": "high",
        "totally_unknown": "dropped",
    })
    row = s.query("SELECT * FROM accident_records WHERE id=?", (rid,))[0]
    assert "totally_unknown" not in row


def test_upsert_source_is_idempotent(tmp_path):
    s = make_store(tmp_path)
    base = {
        "slug": "morth", "organization": "MoRTH", "access_method": "pdf_report",
        "data_type": "accident_stats", "jurisdiction": "IN",
        "status": "pending_verification",
    }
    id1 = s.upsert_source(dict(base))
    id2 = s.upsert_source({**base, "status": "verified"})
    assert id1 == id2
    assert s.count("sources") == 1
    row = s.query("SELECT status FROM sources WHERE slug=?", ("morth",))[0]
    assert row["status"] == "verified"


def test_record_run_and_counts(tmp_path):
    s = make_store(tmp_path)
    s.record_run("morth", "ok", new_count=5, unchanged_count=2)
    s.record_run("bncap", "error", error_count=1, message="timeout")
    assert s.count("run_log") == 2
    rows = s.query("SELECT * FROM run_log ORDER BY id")
    assert rows[0]["status"] == "ok" and rows[0]["new_count"] == 5
    assert rows[1]["status"] == "error" and rows[1]["error_count"] == 1


def test_exists_by_hash(tmp_path):
    s = make_store(tmp_path)
    s.insert("crash_tests", {
        "program": "Bharat NCAP", "source_slug": "bncap",
        "evidence_class": "observed_fact", "confidence": "high",
        "content_hash": "deadbeef",
    })
    assert s.exists_by_hash("crash_tests", "deadbeef") is True
    assert s.exists_by_hash("crash_tests", "nope") is False


def test_exists_by_hash_rejects_table_without_hash(tmp_path):
    s = make_store(tmp_path)
    with pytest.raises(ValueError):
        s.exists_by_hash("run_log", "x")


def test_enum_and_json_coercion(tmp_path):
    from india_road_safety.models import Severity

    s = make_store(tmp_path)
    rid = s.insert("accident_records", {
        "geography": "India", "geo_level": "national", "year": 2023,
        "severity": Severity.FATAL, "metric": "fatalities",
        "value": 1, "source_slug": "morth",
        "evidence_class": "observed_fact", "confidence": "high",
    })
    row = s.query("SELECT severity FROM accident_records WHERE id=?", (rid,))[0]
    assert row["severity"] == "fatal"

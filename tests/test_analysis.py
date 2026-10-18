from india_road_safety.analysis import accident, vehicles, evidence


def test_collision_breakdown_aggregates():
    rows = [
        {"metric": "collision_accidents", "geo_level": "national", "year": 2022, "label": "X", "value": 60},
        {"metric": "collision_fatalities", "geo_level": "national", "year": 2022, "label": "X", "value": 20},
        {"metric": "collision_accidents", "geo_level": "national", "year": 2022, "label": "Y", "value": 40},
        {"metric": "collision_fatalities", "geo_level": "national", "year": 2022, "label": "Y", "value": 10},
    ]
    b = accident.collision_breakdown(rows, 2022)
    assert b[0]["category"] == "X"
    assert b[0]["accidents"] == 60 and b[0]["fatalities"] == 20
    assert b[0]["accidents_share_pct"] == 60.0


def test_time_of_day_order():
    rows = [
        {"metric": "time_interval_accidents", "geo_level": "national", "year": 2022, "label": "06.00 to 9.00 hrs (Day)", "value": 1},
        {"metric": "time_interval_accidents", "geo_level": "national", "year": 2022, "label": "00.00 to 3.00 hrs (Night)", "value": 1},
        {"metric": "time_interval_accidents", "geo_level": "national", "year": 2022, "label": "15.00 to 18.00 hrs (Day)", "value": 1},
    ]
    b = accident.time_of_day_breakdown(rows, 2022)
    assert b[0]["interval"].startswith("00.00") and b[-1]["interval"].startswith("15.00")


def test_equipment_contrast_no_comparable():
    rows = []
    for _ in range(30):
        rows.append({
            "protocol_version": "adult_max=34;child_max=49",
            "adult_occupant_protection": 20,
            "equipment_tested": "airbag,esc,isofix",
        })
    ec = vehicles.equipment_contrast(rows, min_n=30)
    assert ec["has_comparable_contrast"] is False
    assert all(c["comparable"] is False for c in ec["comparisons"])


def test_evidence_grading_mean():
    g = evidence.grade_sources([{"slug": "s", "status": "verified", "access_method": "pdf_report", "data_type": "accident_stats"}], {"s": 10}, latest_year=2022, build_year=2026)
    assert g[0]["slug"] == "s"
    assert "dimensions" in g[0]
    assert g[0]["mean_score"] >= 0 and g[0]["mean_score"] <= 100


def test_monthly_series_range():
    rows = []
    for m in range(1, 13):
        rows.append({"geo_level": "national", "year": 2022, "month": m, "metric": "accidents", "value": 100+m})
    rs = accident.monthly_series(rows, 2022)
    assert len(rs) == 12
    assert rs[0]["month"] == 1 and rs[11]["month"] == 12

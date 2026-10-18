"""Tests for MoRTH parsers."""

from __future__ import annotations

from india_road_safety.collect import morth
from india_road_safety.models import AccidentRecord, RegistrationExposure
from tests.fixtures.morth_samples import (
    MO_NATIONAL_SERIES_SAMPLE,
    MO_PREFACE_SAMPLE,
    STATE_CSV_SAMPLE,
)


def test_parse_national_series_extracts_core_counts():
    recs = morth.parse_national_series(MO_NATIONAL_SERIES_SAMPLE)
    # 1970: accidents, fatalities, injuries, population, vehicles? + vehicles as exposure?
    # we produce accidents/fatalities/injuries/population and exposure (registrations) when vehicles present
    metrics = {r.metric for r in recs if r.year == 1970 and isinstance(r, AccidentRecord)}
    assert "accidents" in metrics
    assert "fatalities" in metrics
    assert "injuries" in metrics
    assert "population" in metrics

    # 2022 core counts
    acc22 = next((r.value for r in recs if r.year == 2022 and r.metric == "accidents"), None)
    fat22 = next((r.value for r in recs if r.year == 2022 and r.metric == "fatalities"), None)
    assert acc22 == 461312
    assert fat22 == 168491

    # exposure (registrations) emitted as RegistrationExposure only for years
    # that carry the full column set (e.g. 2010). 2021/2022 rows are truncated
    # and have no vehicles column, so they yield no exposure record.
    regs_2010 = [x for x in recs if isinstance(x, RegistrationExposure) and x.year == 2010]
    assert len(regs_2010) == 1
    assert regs_2010[0].value == 127746
    assert regs_2010[0].unit == "thousand"
    regs_2022 = [x for x in recs if isinstance(x, RegistrationExposure) and x.year == 2022]
    assert len(regs_2022) == 0


def test_parse_preface_narrative_road_type_and_risk_factors():
    recs = morth.parse_preface_narrative(MO_PREFACE_SAMPLE)
    by_metric = {}
    for r in recs:
        by_metric.setdefault(r.metric, []).append(r)

    # road type accidents
    nh = next(r for r in by_metric.get("accidents", []) if r.road_type == "national_highway")
    assert nh.value == 151997
    sh = next(r for r in by_metric.get("accidents", []) if r.road_type == "state_highway")
    assert sh.value == 106682
    oth = next(r for r in by_metric.get("accidents", []) if r.road_type == "other_road")
    assert oth.value == 202633

    # road type fatalities
    nh_f = next(r for r in by_metric.get("fatalities", []) if r.road_type == "national_highway")
    assert nh_f.value == 61038
    sh_f = next(r for r in by_metric.get("fatalities", []) if r.road_type == "state_highway")
    assert sh_f.value == 41012
    oth_f = next(r for r in by_metric.get("fatalities", []) if r.road_type == "other_road")
    assert oth_f.value == 66441

    # risk factors present as percent metrics
    assert by_metric["overspeeding_share_of_deaths"][0].value == 71.2
    assert by_metric["overspeeding_share_of_deaths"][0].unit == "percent"
    assert by_metric["overspeeding_share_of_accidents"][0].value == 72.3


def test_parse_state_accidents_csv():
    recs = morth.parse_state_accidents_csv(STATE_CSV_SAMPLE)
    # 4 states x 5 years
    assert len(recs) == 20
    ap24 = next(r for r in recs if r.geography == "Andhra Pradesh" and r.year == 2024)
    assert ap24.value == 19557
    tn22 = next(r for r in recs if r.geography == "Tamil Nadu" and r.year == 2022)
    assert tn22.value == 64105
    # geo_level is state
    assert all(r.geo_level == "state" for r in recs)


def test_state_csv_excludes_aggregate_rows():
    text = (
        "Sl No,State,2024 Accidents\n"
        "1,Andhra Pradesh,\"19,557\"\n"
        "2,All India,\"4,87,707\"\n"
        "3,,\n"
    )
    recs = morth.parse_state_accidents_csv(text)
    names = {r.geography for r in recs}
    assert names == {"Andhra Pradesh"}


def test_fatalities_not_confused_with_accident_totals():
    # Regression: the real report reads "...1,51,997 (32.9%) took place on the
    # National Highways ... Out of the total of 1,68,491 fatalities reported in
    # 2022, 61,038 (36.2%) were on National Highways...". The NH fatalities must
    # be 61,038 (not the earlier accident figure 1,51,997).
    text = (
        "fatalities by category of roads. During 2022, a total of 4,61,312 "
        "accidents were recorded in the country, of which, 1,51,997 (32.9%) took "
        "place on the National Highways (NH) including Expressways, 1,06,682 "
        "(23.1%) on State Highways (SH) and the remaining 2,02,633 (43.9%) on "
        "Other Roads. Out of the total of 1,68,491 fatalities reported in 2022, "
        "61,038 (36.2%) were on National Highways, 41,012 (24.3%) were on State "
        "Highways and 66,441 (39.4%) were on Other Roads."
    )
    recs = morth.parse_preface_narrative(text)
    fat = {r.road_type: r.value for r in recs if r.metric == "fatalities" and r.road_type}
    assert fat["national_highway"] == 61038
    assert fat["state_highway"] == 41012
    assert fat["other_road"] == 66441


def test_national_series_bounded_to_annexure1():
    # Regression: the report has decadal-chart and population tables whose rows
    # also start with a year. Only the Annexure 1 block must be parsed, so the
    # population value (5,39,000) must never be recorded as an accident count.
    text = """
    Chart 1.6: Decadal Trend
    1970 114 15 70 1401 915
    ...
    The population and number of vehicles (1970 - 2022)
    1970 5,39,000 21.2 2.7 1,401 814.4 103.5 1
    ...
    Road Accidents, Persons Killed and Injured: 1970-2022
    1970 1,14,100 14,500 70,100 5,39,000 1,401 # 21.2 814.4
    Total Number of Road Accidents in India: 2019 to 2022
    1970 999 999
    """
    recs = morth.parse_national_series(text)
    acc1970 = [r.value for r in recs if isinstance(r, AccidentRecord) and r.year == 1970 and r.metric == "accidents"]
    assert acc1970 == [114100]
    pop1970 = [r.value for r in recs if isinstance(r, AccidentRecord) and r.year == 1970 and r.metric == "population"]
    assert pop1970 == [539000]

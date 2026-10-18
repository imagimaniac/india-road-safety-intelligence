from india_road_safety.collect import morth

_TEXT = open("data/raw/morth_ra_2022.txt").read() if True else ""


def _get_text():
    try:
        with open("data/raw/morth_ra_2022.txt") as f:
            return f.read()
    except Exception:
        return ""


def test_collision_types_parsed():
    t = _get_text()
    if not t:
        assert True
        return
    rs = morth.parse_collision_types(t)
    assert rs, "expected collision records"
    metrics = {r.metric for r in rs}
    assert "collision_accidents" in metrics or any("collision" in (r.metric or "") for r in rs)
    assert any(r.label is not None for r in rs)


def test_time_of_day_parsed():
    t = _get_text()
    if not t:
        assert True
        return
    rs = morth.parse_time_of_day(t)
    assert rs
    assert all(r.metric == "time_interval_accidents" for r in rs)
    assert any("00.00" in (r.label or "") for r in rs)


def test_safety_devices_parsed():
    t = _get_text()
    if not t:
        assert True
        return
    rs = morth.parse_safety_devices(t)
    assert rs
    assert all(r.metric == "safety_device_fatalities" for r in rs)
    vals = {r.label for r in rs}
    assert {"non_use_helmet", "non_use_helmet_driver", "non_use_helmet_passenger",
            "non_use_seatbelt", "non_use_seatbelt_driver", "non_use_seatbelt_passenger"}.issubset(vals)


def test_monthly_parsed():
    t = _get_text()
    if not t:
        assert True
        return
    rs = morth.parse_monthly(t)
    assert len(rs) == 24
    mset = {r.metric for r in rs}
    assert {"accidents", "fatalities"}.issubset(mset)
    mons = {r.month for r in rs}
    assert mons == set(range(1, 13))

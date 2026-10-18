from datetime import date

from india_road_safety.normalize import (
    canonical_category,
    clean_text,
    collapse_ws,
    content_hash,
    normalize_key,
    normalize_manufacturer,
    parse_date,
    parse_float,
    parse_int,
    parse_year,
    parse_year_month,
    slugify,
    stable_id,
)


def test_clean_text_and_collapse():
    assert collapse_ws("  a   b\n\tc ") == "a b c"
    assert clean_text("Maruti&amp;Suzuki") == "Maruti&Suzuki"
    assert clean_text(None) == ""


def test_slugify_and_key():
    assert slugify("Maruti Suzuki") == "maruti-suzuki"
    assert slugify("") == ""
    assert normalize_key("Mahindra  XUV700!") == "mahindra xuv700"


def test_normalize_manufacturer_strips_noise():
    assert normalize_manufacturer("Maruti Suzuki India Limited") == "maruti suzuki"
    assert normalize_manufacturer("Tata Motors Ltd") == "tata"
    assert normalize_manufacturer(None) == ""


def test_content_hash_is_stable_and_sensitive():
    a = content_hash("Accidents", 2023, 100)
    b = content_hash(" accidents ", "2023", "100")
    c = content_hash("Accidents", 2023, 101)
    assert a == b          # normalised
    assert a != c          # value changed
    assert len(a) == 64


def test_content_hash_none_equals_empty_string():
    assert content_hash(None, "x") == content_hash("", "x")


def test_stable_id_prefix():
    sid = stable_id("src", "morth", 2023)
    assert sid.startswith("src-")
    assert len(sid) == 4 + 16


def test_parse_int_indian_grouping_and_missing():
    assert parse_int("1,23,456") == 123456
    assert parse_int("1 234") == 1234
    assert parse_int("₹ 4,500") == 4500
    assert parse_int("1234.0") == 1234
    assert parse_int("N/A") is None
    assert parse_int("") is None
    assert parse_int(None) is None
    assert parse_int("abc") is None
    assert parse_int(float("nan")) is None


def test_parse_float():
    assert parse_float("12.5%") == 12.5
    assert parse_float("1,234.50") == 1234.5
    assert parse_float("unknown") is None
    assert parse_float("-") is None


def test_parse_date_formats_and_no_invention():
    assert parse_date("2024-03-15") == date(2024, 3, 15)
    assert parse_date("15-03-2024") == date(2024, 3, 15)
    assert parse_date("15/03/2024") == date(2024, 3, 15)
    assert parse_date("15 Mar 2024") == date(2024, 3, 15)
    assert parse_date("March 2024") is None      # no day -> None, not invented
    assert parse_date("not a date") is None
    assert parse_date(None) is None


def test_parse_year_month():
    assert parse_year_month("2024-01") == (2024, 1)
    assert parse_year_month("Jan 2024") == (2024, 1)
    assert parse_year_month("Sept 2024") == (2024, 9)
    assert parse_year_month("2024") is None       # year alone is not year-month


def test_parse_year():
    assert parse_year("FY2023") == 2023
    assert parse_year("2024-25") == 2024
    assert parse_year("abc") is None


def test_canonical_category_no_force_fit():
    mapping = {"fatal": "fatal", "grievous injury": "serious"}
    assert canonical_category("Fatal", mapping) == "fatal"
    assert canonical_category("grievous injury", mapping) == "serious"
    assert canonical_category("something else", mapping) is None
    assert canonical_category(None, mapping) is None

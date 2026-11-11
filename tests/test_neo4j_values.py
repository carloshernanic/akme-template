"""Conversao de valores e identidade do no para a carga em Cypher."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from akme.tools.neo4j_values import TYPES, convert, filled, name, node_id


@pytest.mark.parametrize("kind,value,expected", [
    ("integer", "7", 7), ("integer", "7.0", 7), ("integer", 100.0, 100), ("integer", 100, 100),
    ("float", "10.50", 10.5), ("float", Decimal("1.25"), 1.25), ("float", 7, 7.0), ("float", 0.00001, 0.00001),
    ("date", "2026-01-02", date(2026, 1, 2)), ("date", datetime(2026, 1, 2), date(2026, 1, 2)),
    ("date", date(2026, 7, 3), date(2026, 7, 3)), ("string", 12, "12"),
])
def test_convert_accepts(kind, value, expected):
    result = convert(kind, value)
    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize("kind,value", [
    ("integer", "7.5"), ("integer", str(2**63)), ("float", "abc"), ("date", "2026-01-02T10:00:00"),
    ("integer", True), ("date", "02/01/2026"),
    ("integer", "007"), ("integer", "abc"), ("float", "nan"), ("float", "inf"), ("float", "4.120,50"),
    ("float", True), ("date", datetime(2026, 7, 3, 12, 30)), ("date", "abc"),
    ("float", "1e999"), ("float", "1e-400"), ("float", Decimal("1e999")), ("float", Decimal("1e-400")),
])
def test_convert_refuses(kind, value):
    with pytest.raises(ValueError):
        convert(kind, value)


def test_convert_refuses_unknown_kind_and_aware_date():
    with pytest.raises(ValueError):
        convert("bool", "x")
    with pytest.raises(ValueError):
        convert("date", "2026-01-02T00:00:00+00:00")


def test_filled_only_false_for_none_and_empty():
    assert not filled(None) and not filled("")
    assert filled(0) and filled(False) and filled(" ")


def test_types():
    assert TYPES == ("string", "integer", "float", "date")


def test_node_id_does_not_collide():
    assert node_id(["a/b", "c"]) != node_id(["a", "b/c"])
    assert node_id(["1001", "CIM-50"]) == "1001/CIM-50"
    assert node_id(["a b", "c/d"]) == "a%20b/c%2Fd"


def test_name_doubles_backtick():
    assert name("a`b") == "`a``b`"


def test_convert_float_rounds_long_decimals_to_float64():
    assert convert("float", "0.1234567890123456789") == 0.12345678901234568
    assert convert("float", "0e5") == 0.0

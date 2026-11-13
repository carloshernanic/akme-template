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


@pytest.mark.parametrize("identifier", ["a\\u0060b", "Cliente\\U00000060", "a\nb", "a\x00b", "a\tb", "a\x7fb"])
def test_name_refuses_unicode_escape_and_control_characters(identifier):
    with pytest.raises(ValueError, match="identificador"):
        name(identifier)


def test_name_accepts_backslash_without_u_and_accents():
    assert name("a\\b") == "`a\\b`"
    assert name("Região do Cliente") == "`Região do Cliente`"


def test_caption_uses_label_short_key_and_extra_value():
    from akme.tools.neo4j_values import caption
    assert caption("Pedido", ["1001"], "2026-07-03") == "Pedido 1001 2026-07-03"
    assert caption("ItemPedido", ["e481f51cbdc54678b7cc49136f2d6af7", "1"], "29.99") == "ItemPedido e481f51c/1 29.99"
    assert caption("Cliente", ["Sao Paulo/SP"], None) == "Cliente Sao Paulo/SP", "chave que e texto nao e cortada"
    assert caption("Curso", ["Engenharia de Computação"], "EC") == "Curso Engenharia de Computação EC"
    assert caption("Cliente", ["1"], "") == "Cliente 1"
    assert caption("Avaliacao", ["x"], "texto   com\nquebra " + "a" * 60) == "Avaliacao x " + ("texto com quebra " + "a" * 60)[:40]
    assert caption("Produto", ["1"], 0) == "Produto 1 0"


def test_caption_alone_is_the_value_and_falls_back_to_label_and_key():
    from akme.tools.neo4j_values import caption
    assert caption("Projeto", ["P01"], "Plataforma DIGEST", alone=True) == "Plataforma DIGEST"
    assert caption("Projeto", ["P01"], "  Plataforma \n DIGEST ", alone=True) == "Plataforma DIGEST"
    assert caption("Projeto", ["P01"], "", alone=True) == "Projeto P01", "linha sem o valor: classe e chave"
    assert caption("Projeto", ["P01"], None, alone=True) == "Projeto P01"
    assert caption("Projeto", ["P01"], "x" * 80, alone=True) == "x" * 60


def test_reserved_problem_names_the_reason_and_the_way_out():
    from akme.tools.neo4j_values import reserved_problem
    assert "ConceitoRubrica" in reserved_problem("class", "Conceito")
    assert reserved_problem("class", "ConceitoRubrica") is None
    assert "lowerCamelCase" in reserved_problem("relation", "TEM_TERMO")
    assert reserved_problem("relation", "temTermo") is None
    assert "Renomeie a coluna na origem" in reserved_problem("column", "_id")
    assert reserved_problem("column", "id") is None


# --- rodada final: caractere invisivel em nome de fonte, coluna ou relacao ---

@pytest.mark.parametrize("raw,shown", [
    ("﻿product_category_name", "<U+FEFF>product_category_name"),
    ("id​cliente", "id<U+200B>cliente"), ("id cliente", "id<U+00A0>cliente"),
    ("id\x01cliente", "id<U+0001>cliente"), ("nome cliente", "nome cliente"), ("Sao Paulo", "Sao Paulo"),
])
def test_visible_marks_invisible_characters(raw, shown):
    from akme.tools.neo4j_values import visible

    assert visible(raw) == shown


def test_invisible_hint_names_the_character_and_says_what_to_do():
    from akme.tools.neo4j_values import invisible_hint

    assert invisible_hint(["id_cliente", "nome cliente"]) == ""
    hint = invisible_hint(["﻿product_category_name"])
    assert "<U+FEFF>" in hint and "BOM" in hint and "invisivel" in hint
    assert "﻿" not in hint and "sem esse caractere" in hint


def test_caption_alone_with_only_spaces_falls_back_to_label_and_key():
    from akme.tools.neo4j_values import caption
    assert caption("Cliente", [123], "   ", alone=True) == "Cliente 123"

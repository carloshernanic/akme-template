"""Conversao de valores e identidade do no para a carga em Cypher.

Os valores vao ao Neo4j como parametros tipados do driver. As regras de aceitacao e recusa sao as mesmas do antigo
rdf_literal: o que perderia informacao levanta ValueError, nada e descartado em silencio.
"""
from __future__ import annotations

import math
import re
from collections.abc import Sequence
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

from ..models import SOURCE_TYPES

TYPES = SOURCE_TYPES
INT64_MAX = 2**63 - 1
_NUMBER = re.compile(r"-?\d+(\.\d+)?([eE][-+]?\d+)?$")
_INTEGER = re.compile(r"-?(0|[1-9]\d*)(\.0+)?$")


def filled(value: Any) -> bool:
    """Falso so para None e texto vazio; 0 e False sao valores."""
    return value not in (None, "")


def convert(kind: str, value: Any) -> str | int | float | date:
    """Valor Python no tipo declarado. Levanta ValueError quando a conversao perderia informacao."""
    if kind == "string":
        return str(value)
    if kind == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if parsed.time() != time.min or parsed.tzinfo:
            raise ValueError(f"data com horario: {value}")
        return parsed.date()
    if isinstance(value, bool):
        raise ValueError(f"booleano em coluna numerica: {value}")
    text = str(value)
    if kind == "integer" and _INTEGER.match(text) and -INT64_MAX - 1 <= int(text.split(".")[0]) <= INT64_MAX:
        return int(text.split(".")[0])
    if kind == "float" and _NUMBER.match(text):
        try:
            exact = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"valor invalido para float: {value}") from exc
        number = float(exact)
        # estouro vira inf e underflow vira 0.0: dado diferente da origem, recusa
        if not math.isfinite(number) or (number == 0.0 and exact != 0):
            raise ValueError(f"valor fora do intervalo de float: {value}")
        return number
    raise ValueError(f"valor invalido para {kind}: {value}")


def node_id(values: Sequence[Any]) -> str:
    """Identidade do no: cada valor da chave codificado e unido por barra, sem colisao entre ("a/b","c") e ("a","b/c")."""
    return "/".join(quote(str(v), safe="") for v in values)


CAPTION_KEY = 8  # caracteres de cada valor da chave na legenda
CAPTION_EXTRA = 40  # caracteres do valor que completa a legenda


def caption(label: str, key_values: Sequence[Any], extra: Any = None) -> str:
    """Legenda `name` de um no de dado, que o Neo4j Browser mostra na bolinha: o label, os primeiros 8 caracteres de
    cada valor da chave (unidos por barra, sem percent-encoding) e, se preenchido, o valor da coluna de legenda do
    plano (espacos colapsados, ate 40 caracteres). Deterministica: so depende da linha."""
    text = f"{label} " + "/".join(str(v)[:CAPTION_KEY] for v in key_values)
    if filled(extra):
        text += " " + " ".join(str(extra).split())[:CAPTION_EXTRA]
    return text.rstrip()


# barra invertida + u: o Cypher troca escapes unicode antes do parser, inclusive dentro de crases (barra + u0060 e uma crase)
_UNSAFE = re.compile(r"\\[uU]|[\x00-\x1f\x7f]")


def name(identifier: str) -> str:
    """Identificador Cypher entre crases, dobrando a crase. Dados vao sempre como parametro, nunca por aqui.

    Recusa (ValueError) identificador com escape unicode (barra invertida + u) ou caractere de controle: o escape
    poderia virar uma crase e fechar o identificador; o plano transforma a recusa em problema."""
    if _UNSAFE.search(identifier):
        shown = re.sub(r"[\x00-\x1f\x7f]", "?", identifier)
        raise ValueError(f"identificador recusado: '{shown}' tem barra invertida seguida de u ou caractere de controle; "
                         "renomeie a classe, relacao ou coluna")
    return "`" + identifier.replace("`", "``") + "`"



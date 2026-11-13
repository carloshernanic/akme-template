"""Bugs de dados do teste de ponta a ponta de 2026-11-11: BOM no CSV (item 14) e gravacao concorrente (item 6)."""
from __future__ import annotations

import os

import pytest

from akme import project as project_mod
from akme.adapters import load_adapter
from akme.project import read_yaml, remove_file, write_text_atomic, write_yaml
from akme.tools import ontology_write
from akme.tools.sources import check_source


def _bom_csv(project):
    (project.root / "data" / "traducao.csv").write_text(
        "﻿nome_categoria,nome_ingles\nmoveis,furniture\nbrinquedos,toys\n", encoding="utf-8")


def test_csv_with_bom_has_clean_column_names(project):
    _bom_csv(project)
    adapter = load_adapter("local_folder", project.adapter_options())
    assert [c["name"] for c in adapter.read_schema("traducao")["columns"]] == ["nome_categoria", "nome_ingles"]
    assert adapter.read_sample("traducao", 1)[0]["nome_categoria"] == "moveis"


def test_source_key_on_bom_column_is_accepted(project):
    _bom_csv(project)
    checked = check_source(project, {"source": "traducao", "key": ["nome_categoria"]})
    assert checked["checked"]["rows"] == 2


def test_write_is_atomic_and_leaves_no_temp(tmp_path):
    path = tmp_path / "pending" / "x.yml"
    write_yaml(path, {"a": 1})
    write_yaml(path, {"a": 2})
    assert read_yaml(path) == {"a": 2}
    assert os.listdir(path.parent) == ["x.yml"]


def test_replace_and_remove_retry_while_file_is_locked(tmp_path, monkeypatch):
    """No Windows, o servidor lendo o pendente faz replace/unlink falhar com WinError 32 por instantes."""
    monkeypatch.setattr(project_mod.time, "sleep", lambda s: None)
    real_replace, real_unlink, fails = os.replace, type(tmp_path).unlink, {"replace": 2, "unlink": 2}

    def flaky_replace(src, dst):
        if fails["replace"]:
            fails["replace"] -= 1
            raise PermissionError(32, "em uso por outro processo")
        return real_replace(src, dst)

    def flaky_unlink(self, missing_ok=False):
        if fails["unlink"]:
            fails["unlink"] -= 1
            raise PermissionError(32, "em uso por outro processo")
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(project_mod.os, "replace", flaky_replace)
    monkeypatch.setattr(type(tmp_path), "unlink", flaky_unlink)
    path = tmp_path / "a.txt"
    write_text_atomic(path, "ok")
    assert path.read_text(encoding="utf-8") == "ok"
    remove_file(path)
    assert not path.exists() and fails == {"replace": 0, "unlink": 0}


def test_lock_that_never_ends_still_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(project_mod.time, "sleep", lambda s: None)

    def locked(src, dst):
        raise PermissionError(32, "em uso")

    monkeypatch.setattr(project_mod.os, "replace", locked)
    with pytest.raises(PermissionError):
        write_text_atomic(tmp_path / "a.txt", "x")
    assert os.listdir(tmp_path) == []  # o temporario nao fica para tras


def test_list_pending_skips_file_that_vanished_or_is_empty(project):
    edit = ontology_write.propose_edit(project, "add_glossary", {"acronym": "UF", "meaning": "Unidade federativa"})
    (project.pending_dir / "add_class-meio.yml").write_text("", encoding="utf-8")
    assert [e.id for e in ontology_write.list_pending(project)] == [edit.id]
    assert read_yaml(project.pending_dir / "nao-existe.yml") == {}

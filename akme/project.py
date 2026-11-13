from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

import yaml
from dotenv import load_dotenv  

CONFIG_FILE = "akme.yml"


class Project:
    def __init__(self, root: Path | str = ".") -> None:
        self.root = Path(root).resolve()
        
        env_path = self.root / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)

        self.config: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        path = self.root / CONFIG_FILE
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    @property
    def adapter_name(self) -> str:
        return self.config.get("adapter", "local_folder")

    def adapter_options(self) -> dict[str, Any]:
        opts = dict(self.config.get(self.adapter_name, {}) or {})
        for key, value in list(opts.items()):
            if isinstance(value, str) and value.startswith("env:"):
                opts[key] = os.environ.get(value[4:], "")
        return opts

    @property
    def ontology_dir(self) -> Path:
        return self.root / self.config.get("ontology_dir", "ontology")

    @property
    def schema_path(self) -> Path:
        return self.ontology_dir / "schema.ttl"

    @property
    def content_path(self) -> Path:
        return self.ontology_dir / "content.yml"

    @property
    def manifest_path(self) -> Path:
        return self.ontology_dir / "manifest.yml"

    @property
    def changelog_path(self) -> Path:
        return self.ontology_dir / "changelog.yml"

    @property
    def pending_dir(self) -> Path:
        return self.ontology_dir / "pending"

    @property
    def docs_dir(self) -> Path:
        return self.root / self.config.get("docs_dir", "docs")

    @property
    def profile_path(self) -> Path:
        return self.docs_dir / "profile.json"

    @property
    def catalog_path(self) -> Path:
        return self.docs_dir / "databricks_catalog.json"

    @property
    def validation_path(self) -> Path:
        return self.docs_dir / "validation.json"

    @property
    def name(self) -> str:
        return self.config.get("project", self.root.name)

    @property
    def questions_path(self) -> Path:
        return self.root / self.config.get("questions", "validation/questions.yml")

    def resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path


T = TypeVar("T")


def _retry(fn: Callable[[], T], tries: int = 40, wait: float = 0.05) -> T:
    """No Windows, abrir, trocar ou apagar um arquivo que outro processo esta lendo da PermissionError
    (WinError 32/5) por alguns milissegundos: a pagina de revisao le pending/ enquanto o agente grava."""
    for i in range(tries):
        try:
            return fn()
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(wait)
    raise AssertionError("inalcancavel")


def write_text_atomic(path: Path, text: str) -> None:
    """Grava num temporario da mesma pasta e troca de uma vez: quem le nunca ve o arquivo pela metade."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        _retry(lambda: os.replace(tmp, path))
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def remove_file(path: Path) -> None:
    _retry(lambda: path.unlink(missing_ok=True))


def read_text(path: Path) -> str:
    return _retry(lambda: path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(read_text(path)) or {}
    except FileNotFoundError:  # nao existe, ou foi apagado entre listar a pasta e ler
        return {}


def write_yaml(path: Path, data: Any) -> None:
    write_text_atomic(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False))
    
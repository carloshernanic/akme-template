from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILE = "akme.yml"


class Project:
    def __init__(self, root: Path | str = ".") -> None:
        self.root = Path(root).resolve()
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


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

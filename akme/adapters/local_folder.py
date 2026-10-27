from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .base import Adapter, AdapterError

TEXT_DOCS = {".md", ".txt"}


class LocalFolderAdapter(Adapter):
    name = "local_folder"

    def __init__(self, path: str = ".", encoding: str = "utf-8", delimiter: str = ",") -> None:
        self.path = Path(path)
        self.encoding = encoding
        self.delimiter = delimiter
        if not self.path.is_dir():
            raise AdapterError(f"pasta nao encontrada: {self.path}")

    def _csv(self, source: str) -> Path:
        file = self.path / f"{source}.csv"
        if not file.exists():
            raise AdapterError(f"fonte nao encontrada: {file}")
        return file

    def list_sources(self) -> list[str]:
        return sorted(p.stem for p in self.path.glob("*.csv"))

    def read_schema(self, source: str) -> dict[str, Any]:
        with self._csv(source).open(encoding=self.encoding, newline="") as fh:
            header = next(csv.reader(fh, delimiter=self.delimiter))
        return {"name": source, "columns": [{"name": c, "type": "string"} for c in header]}

    def read_sample(self, source: str, n: int = 100) -> list[dict[str, Any]]:
        with self._csv(source).open(encoding=self.encoding, newline="") as fh:
            reader = csv.DictReader(fh, delimiter=self.delimiter)
            rows = []
            for i, row in enumerate(reader):
                if i >= n:
                    break
                rows.append({k: (v if v != "" else None) for k, v in row.items()})
            return rows

    def read_docs(self) -> list[dict[str, str]]:
        docs = []
        for file in sorted(self.path.iterdir()):
            if file.suffix.lower() in TEXT_DOCS:
                docs.append({"name": file.name, "text": file.read_text(encoding=self.encoding)})
            elif file.suffix.lower() == ".pdf":
                docs.append({"name": file.name, "text": _pdf_text(file)})
        return docs


def _pdf_text(file: Path) -> str:
    try:
        import pypdf
    except ImportError:
        return "[pdf ignorado: instale o extra 'pdf' para extrair texto]"
    reader = pypdf.PdfReader(str(file))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

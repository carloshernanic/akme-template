from typer.testing import CliRunner

from akme.cli import app
from akme.project import read_yaml


def test_init_defaults_to_data_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    assert read_yaml(tmp_path / "akme.yml")["local_folder"] == {"path": "data"}
    assert (tmp_path / "data").is_dir()


def test_init_custom_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(app, ["init", "--path", "dados/cliente"])
    assert read_yaml(tmp_path / "akme.yml")["local_folder"] == {"path": "dados/cliente"}
    assert (tmp_path / "dados" / "cliente").is_dir()

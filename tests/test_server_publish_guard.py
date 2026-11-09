"""A tool MCP nao carrega no Neo4j: quem executa a carga e o humano, na CLI."""
import pytest

from akme import server
from akme.tools import publish as publish_tool


def test_mcp_publish_refuses_neo4j_execution(monkeypatch):
    def must_not_run(*args, **kwargs):
        raise AssertionError("a tool nao pode chegar ao publish real")

    monkeypatch.setattr(publish_tool, "publish", must_not_run)
    monkeypatch.setattr(server, "project", lambda: None)
    with pytest.raises(PermissionError, match="--no-dry-run"):
        server.publish(target="neo4j", dry_run=False)


def test_mcp_publish_still_runs_neo4j_dry_run(monkeypatch):
    calls = []
    monkeypatch.setattr(publish_tool, "publish", lambda *a: calls.append(a) or {"dry_run": True})
    monkeypatch.setattr(server, "project", lambda: "projeto")
    assert server.publish(target="neo4j") == {"dry_run": True}
    assert calls == [("projeto", "neo4j", True, None)]


@pytest.mark.parametrize("target", ["yaml", "snowflake", "databricks", "rdf"])
def test_mcp_publish_keeps_other_targets_unchanged(target, monkeypatch):
    calls = []
    monkeypatch.setattr(publish_tool, "publish", lambda *a: calls.append(a) or {})
    monkeypatch.setattr(server, "project", lambda: "projeto")
    server.publish(target=target, dry_run=False)
    assert calls == [("projeto", target, False, None)]

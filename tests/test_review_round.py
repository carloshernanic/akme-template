import json
import threading
import time
import urllib.request

from akme import review_server
from akme.tools import ontology_write
from akme.tools.review_round import open_round, read_round, wait_for_review
from akme.tools.stage import current_stage

CQ = {"question": "q", "type": "atributos", "concepts": ["X"],
      "evidence": [{"kind": "source", "path": "a", "locator": "1", "quote": "x"}]}


def _cq(project):
    e = ontology_write.propose_edit(project, "add_competency_question", dict(CQ))
    ontology_write.review_edit(project, e.id, "accept", "ana", edits={"priority": "high", "status": "approved"})
    return e


def test_open_round_reuses_waiting_round(seeded):
    _cq(seeded)
    first = open_round(seeded)
    assert first["status"] == "waiting" and first["pending"] == 1
    assert open_round(seeded)["id"] == first["id"]


def test_wait_times_out_while_human_has_not_applied(seeded):
    _cq(seeded)
    rnd = open_round(seeded)
    out = wait_for_review(seeded, rnd["id"], timeout=0.2, poll=0.05)
    assert out["status"] == "waiting" and out["pending"] == 1


def test_wait_returns_applied_when_page_applies(seeded):
    _cq(seeded)
    rnd = open_round(seeded)
    srv = review_server.start(seeded, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        assert urllib.request.urlopen(base + "/api/round").status == 200

        def apply_later():
            time.sleep(0.3)
            req = urllib.request.Request(base + "/api/apply", data=json.dumps({"approved_by": "ana"}).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req).read()

        threading.Thread(target=apply_later, daemon=True).start()
        out = wait_for_review(seeded, rnd["id"], timeout=10, poll=0.05)
        assert out["status"] == "applied"
        assert out["round"]["approved_by"] == "ana" and out["round"]["via"] == "page"
        assert out["round"]["applied"] == 1 and out["pending_left"] == 0
        assert isinstance(out["checklist"], list) and out["checklist"]
        data = json.loads(urllib.request.urlopen(base + "/api/data").read())
        assert data["round"]["status"] == "applied"
    finally:
        srv.shutdown()
        srv.server_close()


def test_chat_apply_closes_round_and_wrong_id_is_no_round(seeded):
    _cq(seeded)
    rnd = open_round(seeded)
    assert wait_for_review(seeded, "R-outra", timeout=0)["status"] == "no_round"
    ontology_write.apply_reviewed(seeded, "bia")
    assert read_round(seeded)["via"] == "chat"
    assert wait_for_review(seeded, rnd["id"], timeout=0)["status"] == "applied"


def test_wait_returns_nothing_pending_when_queue_empties_elsewhere(seeded):
    e = ontology_write.propose_edit(seeded, "add_competency_question", dict(CQ))
    rnd = open_round(seeded)
    ontology_write.reject_edit(seeded, e.id, "ana", "nao serve")
    assert wait_for_review(seeded, rnd["id"], timeout=0)["status"] == "nothing_pending"


def test_stage_returns_checklist_for_current_stage(project):
    st = current_stage(project)
    assert st["number"] == 1
    texts = [s["text"] for s in st["checklist"]]
    assert any("Dez CQs" in t for t in texts) and any("Requisitos fechados" in t for t in texts)
    assert all(s["done"] in (True, False, None) and "tools" in s for s in st["checklist"])
    review = next(s for s in st["checklist"] if s["text"].startswith("Humano revisou"))
    assert review["done"] is False  # nada proposto ainda nao conta como revisado

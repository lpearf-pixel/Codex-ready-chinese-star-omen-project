from __future__ import annotations

import json
import subprocess


def test_smoke_payload_check_script_runs():
    proc = subprocess.run(
        ["python", "scripts/kb_search_smoke.py", "--mode", "payload-check"],
        check=True,
        capture_output=True,
        text=True,
    )
    out = json.loads(proc.stdout)
    assert out["mode"] == "payload_check"
    assert out["checks"]["knowledge_mode"] is True
    assert out["checks"]["evidence_mode"] is True
    assert out["checks"]["evidence_literal_first"] is True
    assert out["checks"]["retrieval_pool_present"] is True


def test_smoke_corpus_eval_mode_runs():
    proc = subprocess.run(
        ["python", "scripts/kb_search_smoke.py", "--mode", "corpus-eval"],
        check=True,
        capture_output=True,
        text=True,
    )
    out = json.loads(proc.stdout)
    assert out["mode"] == "corpus_eval"
    assert out["all_mode_match"] is True

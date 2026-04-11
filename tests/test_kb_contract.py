from src.connectors.kb_contract import can_be_final_fact, is_final_citable, resolve_evidence_level


def test_final_citable_primary_cards():
    assert is_final_citable("fenjuan")
    assert is_final_citable("fulltext")


def test_non_citable_prompt_asset():
    assert not is_final_citable("prompt_asset")
    assert not can_be_final_fact("prompt_asset")


def test_resolve_evidence_level():
    assert resolve_evidence_level("term_card") == "structured"

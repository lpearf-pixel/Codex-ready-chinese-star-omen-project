from src.connectors.kb_contract import can_be_final_fact, infer_metadata_from_path, is_final_citable, resolve_evidence_level


def test_final_citable_primary_cards():
    assert is_final_citable("fenjuan")
    assert is_final_citable("fulltext")


def test_non_citable_prompt_asset():
    assert not is_final_citable("prompt_asset")
    assert not can_be_final_fact("prompt_asset")


def test_resolve_evidence_level():
    assert resolve_evidence_level("term_card") == "structured"


def test_infer_zhusu_card_from_path():
    meta = infer_metadata_from_path("/docs/古籍/唐開元占經/逐宿卡/心宿.md")
    assert meta["book_title"] == "唐開元占經"
    assert meta["book_id"] == "kaiyuan_zhanjing"
    assert meta["card_type"] == "zhusu_card"
    assert meta["evidence_level"] == "structured"


def test_infer_fenjuan_from_path():
    meta = infer_metadata_from_path("/docs/古籍/唐開元占經/分卷/卷十二.md")
    assert meta["book_id"] == "kaiyuan_zhanjing"
    assert meta["card_type"] == "fenjuan"
    assert meta["evidence_level"] == "primary"


def test_infer_fulltext_from_path():
    meta = infer_metadata_from_path("/docs/古籍/唐開元占經/全文合併版.md")
    assert meta["book_id"] == "kaiyuan_zhanjing"
    assert meta["card_type"] == "fulltext"
    assert meta["evidence_level"] == "primary"

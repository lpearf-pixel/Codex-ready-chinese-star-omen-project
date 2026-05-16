from src.connectors.kb_contract_adapter import adapt_kb_payload


def test_adapter_priority_top_level_over_frontmatter_and_path():
    payload = {
        "kb_book_id": "top_book",
        "book_title": "Top Title",
        "card_type": "term_card",
        "evidence_level": "structured",
        "final_citable": False,
        "query_mode_hint": "knowledge",
        "frontmatter": {
            "kb_book_id": "front_book",
            "book_title": "Front Title",
            "card_type": "fenjuan",
            "evidence_level": "primary",
            "final_citable": True,
            "query_mode_hint": "evidence",
        },
        "path": "/docs/古籍/唐開元占經/分卷/KR3g0018_031.md",
    }
    adapted = adapt_kb_payload(payload)
    assert adapted.kb_book_id == "top_book"
    assert adapted.book_title == "Top Title"
    assert adapted.card_type == "term_card"
    assert adapted.evidence_level == "structured"
    assert adapted.final_citable is False
    assert adapted.query_mode_hint == "knowledge"


def test_adapter_uses_frontmatter_before_path():
    adapted = adapt_kb_payload(
        {
            "frontmatter": {
                "kb_book_id": "front_book",
                "book_title": "Front Title",
                "card_type": "term_card",
                "evidence_level": "structured",
            },
            "path": "/docs/古籍/唐開元占經/分卷/KR3g0018_031.md",
        }
    )
    assert adapted.kb_book_id == "front_book"
    assert adapted.card_type == "term_card"


def test_adapter_path_fallback_and_deprecated_book_id():
    path_adapted = adapt_kb_payload({"path": "/docs/古籍/唐開元占經/分卷/KR3g0018_031.md"})
    assert path_adapted.kb_book_id == "kaiyuan_zhanjing"
    assert path_adapted.card_type == "fenjuan"
    legacy = adapt_kb_payload({"book_id": "legacy", "card_type": "fenjuan"})
    assert legacy.kb_book_id == "legacy"
    assert legacy.deprecated_fields_used == ["book_id"]

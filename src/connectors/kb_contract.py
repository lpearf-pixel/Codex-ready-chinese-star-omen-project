from __future__ import annotations

from enum import Enum
from typing import Any


class CardType(str, Enum):
    FENJUAN = "fenjuan"
    FULLTEXT = "fulltext"
    XINGGUAN_CARD = "xingguan_card"
    ZHUSU_CARD = "zhusu_card"
    TERM_CARD = "term_card"
    EXTRACT_CARD = "extract_card"
    TOPIC_INDEX = "topic_index"
    CHAPTER_SUMMARY = "chapter_summary"
    NAV = "nav"
    PROMPT_ASSET = "prompt_asset"
    QA_EXAMPLE = "qa_example"


class EvidenceLevel(str, Enum):
    PRIMARY = "primary"
    STRUCTURED = "structured"
    INDEX = "index"
    PROMPT = "prompt"
    EXAMPLE = "example"


PROOF_PRIORITY: list[CardType] = [
    CardType.FENJUAN,
    CardType.FULLTEXT,
    CardType.XINGGUAN_CARD,
    CardType.ZHUSU_CARD,
    CardType.TERM_CARD,
    CardType.EXTRACT_CARD,
    CardType.TOPIC_INDEX,
    CardType.CHAPTER_SUMMARY,
    CardType.NAV,
    CardType.PROMPT_ASSET,
    CardType.QA_EXAMPLE,
]

FINAL_CITABLE_CARD_TYPES: set[CardType] = {CardType.FENJUAN, CardType.FULLTEXT}
NON_FACTUAL_CARD_TYPES: set[CardType] = {CardType.PROMPT_ASSET, CardType.QA_EXAMPLE}

STAGE1_RECALL_CARD_TYPES: list[CardType] = [
    CardType.XINGGUAN_CARD,
    CardType.ZHUSU_CARD,
    CardType.TERM_CARD,
    CardType.EXTRACT_CARD,
    CardType.TOPIC_INDEX,
    CardType.CHAPTER_SUMMARY,
]

STAGE2_PRIMARY_CARD_TYPES: list[CardType] = [CardType.FENJUAN, CardType.FULLTEXT]

CARD_TYPE_TO_EVIDENCE_LEVEL: dict[CardType, EvidenceLevel] = {
    CardType.FENJUAN: EvidenceLevel.PRIMARY,
    CardType.FULLTEXT: EvidenceLevel.PRIMARY,
    CardType.XINGGUAN_CARD: EvidenceLevel.STRUCTURED,
    CardType.ZHUSU_CARD: EvidenceLevel.STRUCTURED,
    CardType.TERM_CARD: EvidenceLevel.STRUCTURED,
    CardType.EXTRACT_CARD: EvidenceLevel.STRUCTURED,
    CardType.TOPIC_INDEX: EvidenceLevel.INDEX,
    CardType.CHAPTER_SUMMARY: EvidenceLevel.INDEX,
    CardType.NAV: EvidenceLevel.INDEX,
    CardType.PROMPT_ASSET: EvidenceLevel.PROMPT,
    CardType.QA_EXAMPLE: EvidenceLevel.EXAMPLE,
}


PATH_CARD_TYPE_RULES: list[tuple[str, str]] = [
    ("/分卷/", CardType.FENJUAN.value),
    ("全文合併版", CardType.FULLTEXT.value),
    ("全文合并版", CardType.FULLTEXT.value),
    ("/星官卡/", CardType.XINGGUAN_CARD.value),
    ("/逐宿卡/", CardType.ZHUSU_CARD.value),
    ("/术语卡片/", CardType.TERM_CARD.value),
    ("/知识抽取卡/", CardType.EXTRACT_CARD.value),
    ("/主题索引/", CardType.TOPIC_INDEX.value),
    ("/章节摘要卡/", CardType.CHAPTER_SUMMARY.value),
    ("/导航/", CardType.NAV.value),
    ("/agent/", CardType.PROMPT_ASSET.value),
    ("/prompts/", CardType.PROMPT_ASSET.value),
    ("02-Agent入口.md", CardType.PROMPT_ASSET.value),
    ("schema.yaml", CardType.PROMPT_ASSET.value),
    ("/问答样例库/", CardType.QA_EXAMPLE.value),
]


BOOK_TITLE_TO_ID: dict[str, str] = {
    "唐開元占經": "kaiyuan_zhanjing",
    "唐开元占经": "kaiyuan_zhanjing",
    "開元占經": "kaiyuan_zhanjing",
    "开元占经": "kaiyuan_zhanjing",
}


def is_final_citable(card_type: str) -> bool:
    try:
        return CardType(card_type) in FINAL_CITABLE_CARD_TYPES
    except ValueError:
        return False


def resolve_evidence_level(card_type: str) -> str | None:
    try:
        return CARD_TYPE_TO_EVIDENCE_LEVEL[CardType(card_type)].value
    except ValueError:
        return None


def can_be_final_fact(card_type: str) -> bool:
    try:
        ct = CardType(card_type)
    except ValueError:
        return False
    return ct in FINAL_CITABLE_CARD_TYPES and ct not in NON_FACTUAL_CARD_TYPES


def infer_book_title_from_path(path: str | None) -> str | None:
    if not path:
        return None
    normalized = path.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    for idx, token in enumerate(parts):
        if token == "古籍" and idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def infer_book_id_from_path(path: str | None) -> str | None:
    title = infer_book_title_from_path(path)
    if title:
        return BOOK_TITLE_TO_ID.get(title)
    return None


def infer_card_type_from_path(path: str | None) -> str | None:
    if not path:
        return None
    normalized = path.replace("\\", "/")
    for token, card_type in PATH_CARD_TYPE_RULES:
        if token in normalized:
            return card_type
    return None


def infer_metadata_from_path(path: str | None) -> dict[str, str | None]:
    card_type = infer_card_type_from_path(path)
    return {
        "book_title": infer_book_title_from_path(path),
        "book_id": infer_book_id_from_path(path),
        "card_type": card_type,
        "evidence_level": resolve_evidence_level(card_type) if card_type else None,
    }


def is_citable_evidence(evidence: dict[str, Any]) -> bool:
    card_type = str(evidence.get("card_type") or "")
    evidence_level = str(evidence.get("evidence_level") or "")
    relative_path = evidence.get("relative_path")
    if not relative_path:
        return False

    if evidence_level == EvidenceLevel.PRIMARY.value:
        return True

    return card_type in {CardType.FENJUAN.value, CardType.FULLTEXT.value}

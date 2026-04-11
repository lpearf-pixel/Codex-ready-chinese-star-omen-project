from __future__ import annotations

from enum import Enum


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

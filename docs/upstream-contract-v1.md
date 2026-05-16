# Upstream Contract v1

This document defines the static frontmatter contract owned by the upstream `Local-KB-Unified` repository. It is the contract boundary between source notes and the ingest projection layer.

## Scope

The upstream contract defines **static knowledge semantics only**. It must not store downstream runtime artifacts such as detector output, benchmark results, calibration status, review decisions, or profile state.

## Primary fields

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `kb_book_id` | yes | string | Canonical book identifier and single source of truth. |
| `book_title` | yes | string | Human-readable source title. |
| `card_type` | yes | enum | Static card category. |
| `evidence_level` | yes | enum | Static evidence level. |
| `final_citable` | optional | boolean | Whether this card can be used as final citation evidence. |
| `query_mode_hint` | yes | enum | `knowledge`, `evidence`, or `support`. |
| `aliases` | optional | string[] | Search aliases. |
| `variant_terms` | optional | string[] | Script/form variants. |
| `normalized_terms` | optional | string[] | Normalized terms used by retrieval. |
| `source_locator` | optional | string | Stable human locator such as volume/section. |

`book_id` is deprecated and allowed only as a temporary fallback. Consumers must normalize it into `kb_book_id`.

## Enumerations

`card_type`: `fenjuan`, `fulltext`, `xingguan_card`, `zhusu_card`, `term_card`, `extract_card`, `topic_index`, `chapter_summary`, `nav`, `prompt_asset`, `qa_example`.

`evidence_level`: `primary`, `structured`, `index`, `prompt`, `example`, `candidate`.

`query_mode_hint`: `knowledge`, `evidence`, `support`.

## Layer responsibility

Upstream frontmatter defines static semantics. It does not run business inference and does not contain downstream runtime analysis.

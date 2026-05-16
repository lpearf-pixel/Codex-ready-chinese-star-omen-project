# Consumer Contract v1

This document defines how the downstream Python project consumes upstream and ingest payloads.

## Adapter-first consumption

Downstream consumers must use `src/connectors/kb_contract_adapter.py` to normalize payloads. The adapter emits the standard fields:

- `kb_book_id`
- `book_title`
- `card_type`
- `evidence_level`
- `final_citable`
- `query_mode_hint`
- `aliases`
- `variant_terms`
- `normalized_terms`
- `source_locator`

## Priority order

1. Payload top-level fields.
2. `payload.frontmatter` or `payload.metadata`.
3. Path inference as final fallback.

Deprecated `book_id` is accepted only as fallback and normalized internally to `kb_book_id`.

## CLI behavior

- `search-kb --book-id` maps to `filters.kb_book_id`.
- `inspect-kb --book-id` maps to `filters.kb_book_id`.
- Evidence phrases such as `荧惑守心`, `月犯心宿`, and `五星聚` default to `query_mode=evidence` and `literal_first=true`.
- Entity queries such as `心宿` and `荧惑` default to knowledge mode.

## Validation commands

```bash
python -m src.cli validate-upstream-contract
python -m src.cli validate-payload-contract
python -m src.cli validate-consumer-contract
```

These commands validate the static contract files, payload flattening expectations, and downstream consumer normalization behavior.

# Payload Contract v1

This document defines the ingest projection contract for payloads written by upstream `make ingest` into Qdrant and returned by `kb-search`.

## Required top-level payload fields

After ingest flattening, Qdrant payloads must include these top-level fields:

- `kb_book_id`
- `book_title`
- `card_type`
- `evidence_level`
- `final_citable`
- `query_mode_hint`

Recommended top-level or frontmatter fields:

- `aliases`
- `variant_terms`
- `normalized_terms`
- `source_locator`

`book_id` is deprecated and may appear only as a temporary compatibility fallback. Downstream normalizes it to `kb_book_id`.

## Ingest responsibility

The ingest layer only reads upstream frontmatter and flattens/project fields into payloads. It is not a rule engine, detector, benchmark runner, calibration system, or review store.

## Flattening rule

Downstream consumers expect payload top-level fields first, then `payload.frontmatter`/`payload.metadata`, then path inference as a final fallback. Therefore ingest should flatten the required fields to the payload top level whenever possible.

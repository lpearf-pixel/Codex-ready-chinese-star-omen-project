from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import typer
except ModuleNotFoundError:  # pragma: no cover
    typer = None

try:
    from jsonschema import validate
except ModuleNotFoundError:  # pragma: no cover
    def validate(instance, schema):
        for key in schema.get("required", []):
            if key not in instance:
                raise ValueError(f"Missing required field: {key}")

from src.config.settings import get_settings
from src.connectors.evidence_resolver import resolve_evidence
from src.connectors.kb_contract import STAGE1_RECALL_CARD_TYPES, STAGE2_PRIMARY_CARD_TYPES, is_citable_evidence
from src.connectors.kb_search_retriever import KBSearchRetriever
from src.connectors.manifest_reader import ManifestReader
from src.eval.corpus_eval import run_corpus_eval
from src.rule_engine.minimal_matcher import run_match_rule

app = typer.Typer(help="Chinese astro model CLI") if typer else None


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_data_impl(
    rules_path: Path = Path("data/processed/corpus/sample_rules.json"),
    asterism_path: Path = Path("data/processed/ontology/sample_asterisms.json"),
    rule_schema: Path = Path("schemas/omen_rule.schema.json"),
    asterism_schema: Path = Path("schemas/asterism.schema.json"),
):
    rules = _load_json(rules_path)
    rule_schema_obj = _load_json(rule_schema)
    for rule in rules:
        validate(instance=rule, schema=rule_schema_obj)
    asterisms = _load_json(asterism_path)
    asterism_schema_obj = _load_json(asterism_schema)
    for item in asterisms:
        validate(instance=item, schema=asterism_schema_obj)
    return {"ok": True, "rules": len(rules), "asterisms": len(asterisms)}


def _split_hits(result: dict[str, Any], *, include_raw: bool = False) -> dict[str, Any]:
    filtered_hits = result.get("hits", [])
    structured = [h for h in filtered_hits if h.get("card_type") in [c.value for c in STAGE1_RECALL_CARD_TYPES]]
    primary = [h for h in filtered_hits if h.get("card_type") in [c.value for c in STAGE2_PRIMARY_CARD_TYPES]]
    payload = {
        "normalized_query": result.get("normalized_query"),
        "query_variants": result.get("query_variants", []),
        "exact_hits": result.get("exact_hits", []),
        "related_hits": result.get("related_hits", []),
        "structured_hits": structured,
        "primary_hits": primary,
        "primary_candidates": result.get("primary_candidates", []),
        "structured_fallbacks": result.get("structured_fallbacks", []),
        "fallback_used": result.get("fallback_used", False),
        "files_scanned": result.get("files_scanned", 0),
        "matched_files": result.get("matched_files", []),
        "matched_headings": result.get("matched_headings", []),
    }
    if include_raw:
        payload["raw_hits"] = result.get("raw_hits", [])
        payload["inferred_hits"] = result.get("inferred_hits", [])
        payload["filtered_hits"] = filtered_hits
    return payload


def inspect_kb_impl(
    root: Path | None = None,
    query: str | None = None,
    book_id: str | None = None,
    card_type: list[str] | None = None,
    evidence_level: str | None = None,
    limit: int | None = None,
    show_raw: bool = False,
    base_url: str | None = None,
    api_key: str | None = None,
    collection: str | None = None,
    show_related: bool = False,
):
    settings = get_settings()
    effective_limit = limit if limit is not None else settings.app_default_limit
    if query:
        retriever = KBSearchRetriever(base_url=base_url, api_key=api_key)
        filters: dict[str, Any] = {}
        if book_id:
            filters["book_id"] = book_id
        if card_type:
            filters["card_type"] = card_type
        if evidence_level:
            filters["evidence_level"] = evidence_level
        try:
            stage = retriever.two_stage_retrieve(
                query,
                top_k=effective_limit,
                collection=collection,
                filters=filters or None,
            )
        except Exception as exc:
            return {
                "mode": "search",
                "query": query,
                "root": str(root) if root else None,
                "error": str(exc),
                "hint": "check KB_SEARCH_API_KEY, KB_SEARCH_BASE_URL/KB_SEARCH_API_PORT, and whether kb-search service is running",
            }
        stage1_out = _split_hits(stage.get("stage1", {}), include_raw=show_raw)
        stage2_out = _split_hits(stage.get("stage2", {}), include_raw=show_raw)
        top_hit = (stage.get("stage1", {}).get("hits") or stage.get("stage1", {}).get("inferred_hits") or [None])[0]
        query_mode = stage.get("stage1", {}).get("query_mode", "knowledge")

        if query_mode == "knowledge":
            stage1_out["exact_hits"] = stage1_out.get("exact_hits", [])[:1]
            stage1_out["related_hits"] = stage1_out.get("related_hits", [])[:3] if show_related else []
        elif (
            query_mode == "evidence"
            and not stage2_out.get("structured_fallbacks")
            and not stage2_out.get("primary_hits")
            and not stage2_out.get("primary_candidates")
        ):
            fallback_pool: list[dict[str, Any]] = []
            for key in ("exact_hits", "related_hits", "structured_hits"):
                fallback_pool.extend(stage1_out.get(key, []))
            fallback_pool.extend(stage.get("stage1", {}).get("hits", []))

            deduped: list[dict[str, Any]] = []
            seen: set[str] = set()
            for hit in fallback_pool:
                if hit.get("evidence_level") != "structured":
                    continue
                dedup_key = str(hit.get("chunk_id") or hit.get("path") or hit.get("title") or repr(hit))
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                deduped.append({**hit, "status": "candidate_only"})
            stage2_out["structured_fallbacks"] = deduped

        stage2_out["primary_candidates"] = stage2_out.get("primary_candidates", [])
        stage2_out["structured_fallbacks"] = stage2_out.get("structured_fallbacks", [])

        out = {
            "mode": "search",
            "query": query,
            "query_mode": query_mode,
            "normalized_query": stage1_out.get("normalized_query"),
            "query_variants": stage1_out.get("query_variants", []),
            "root": str(root) if root else None,
            "book_title": top_hit.get("book_title") if isinstance(top_hit, dict) else None,
            "book_id": top_hit.get("book_id") if isinstance(top_hit, dict) else None,
            "exact_hits": stage1_out.get("exact_hits", []),
            "related_hits": stage1_out.get("related_hits", []),
            "primary_candidates": stage2_out.get("primary_candidates", []),
            "structured_fallbacks": stage2_out.get("structured_fallbacks", []),
            "stage1": stage1_out,
            "stage2": stage2_out,
            "note": "if no primary hits, output should be treated as clue/candidate explanation only",
        }
        if show_raw:
            out["raw"] = stage
        return out

    if root:
        reader = ManifestReader(root)
        return {"mode": "local_check", "result": reader.inspect_root()}

    return {"mode": "noop", "message": "provide --query for kb-search or --root for local inspection"}


def resolve_evidence_impl(rule: Path, kb_root: Path | None = None, strict: bool = False):
    settings = get_settings()
    rule_obj = _load_json(rule)
    if isinstance(rule_obj, list):
        if not rule_obj:
            raise ValueError("rule file is an empty array")
        rule_obj = rule_obj[0]

    evidence = rule_obj.get("evidence")
    if not evidence:
        raise ValueError("rule file has no evidence")

    effective_root = kb_root if kb_root else Path(settings.kb_sources_root)
    resolved = resolve_evidence(evidence, effective_root)
    payload = {
        "rule_id": rule_obj.get("id"),
        "kb_book_id": resolved.get("kb_book_id"),
        "note_id": resolved.get("note_id"),
        "relative_path": resolved.get("relative_path"),
        "card_type": resolved.get("card_type"),
        "locator": resolved.get("locator"),
        "anchor_heading": resolved.get("anchor_heading"),
        "quote": resolved.get("quote"),
        "volume": resolved.get("volume"),
        "section": resolved.get("section"),
        "source_locator": resolved.get("source_locator"),
        "heading_path": resolved.get("heading_path"),
        "anchor_text": resolved.get("anchor_text"),
        "paragraph_index": resolved.get("paragraph_index"),
        "ingest_source": resolved.get("ingest_source"),
        "source_type": resolved.get("source_type"),
        "evidence_level": resolved.get("evidence_level"),
        "status": resolved.get("status"),
        "candidate_reason": resolved.get("candidate_reason"),
    }
    if strict and payload["status"] != "citable":
        raise ValueError("当前仅为候选证据，strict 模式拒绝通过")
    return payload


if typer:
    @app.command("validate-data")
    def validate_data(
        rules_path: Path = Path("data/processed/corpus/sample_rules.json"),
        asterism_path: Path = Path("data/processed/ontology/sample_asterisms.json"),
        rule_schema: Path = Path("schemas/omen_rule.schema.json"),
        asterism_schema: Path = Path("schemas/asterism.schema.json"),
    ):
        out = validate_data_impl(rules_path, asterism_path, rule_schema, asterism_schema)
        typer.echo(f"Validation passed: {out['rules']} rules, {out['asterisms']} asterisms")


    @app.command("inspect-kb")
    def inspect_kb(
        root: Path | None = typer.Option(None, "--root"),
        query: str | None = typer.Option(None, "--query"),
        book_id: str | None = typer.Option(None, "--book-id"),
        card_type: list[str] | None = typer.Option(None, "--card-type"),
        evidence_level: str | None = typer.Option(None, "--evidence-level"),
        limit: int | None = typer.Option(None, "--limit"),
        collection: str | None = typer.Option(None, "--collection"),
        base_url: str | None = typer.Option(None, "--base-url"),
        api_key: str | None = typer.Option(None, "--api-key"),
        show_related: bool = typer.Option(False, "--show-related"),
        show_raw: bool = typer.Option(False, "--show-raw"),
    ):
        out = inspect_kb_impl(root, query, book_id, card_type, evidence_level, limit, show_raw, base_url, api_key, collection, show_related)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("resolve-evidence")
    def resolve_evidence_cmd(
        rule: Path = typer.Option(..., "--rule"),
        kb_root: Path | None = typer.Option(None, "--kb-root"),
        pretty: bool = typer.Option(False, "--pretty"),
        strict: bool = typer.Option(False, "--strict"),
    ):
        out = resolve_evidence_impl(rule, kb_root=kb_root, strict=strict)
        if pretty:
            typer.echo("\n".join(f"{k}: {v}" for k, v in out.items()))
            if out["status"] != "citable":
                typer.echo("当前仅为候选证据")
        else:
            typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("search-kb")
    def search_kb(
        query: str,
        book_id: str | None = None,
        card_type: list[str] | None = None,
        evidence_level: str | None = None,
        top_k: int | None = None,
        collection: str | None = None,
        query_mode: str | None = None,
        literal_first: bool | None = None,
        literal_pool_factor: int | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        retriever = KBSearchRetriever(base_url=base_url, api_key=api_key)
        filters: dict[str, Any] = {}
        if book_id:
            filters["book_id"] = book_id
        if card_type:
            filters["card_type"] = card_type
        if evidence_level:
            filters["evidence_level"] = evidence_level
        result = retriever.search(
            query,
            top_k=top_k,
            collection=collection,
            filters=filters or None,
            query_mode=query_mode,
            literal_first=literal_first,
            literal_pool_factor=literal_pool_factor,
        )
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


    @app.command("audit-rules")
    def audit_rules(rules_path: Path = Path("data/processed/corpus/sample_rules.json"), kb_root: Path | None = None):
        settings = get_settings()
        rules = _load_json(rules_path)
        if not isinstance(rules, list):
            raise typer.BadParameter("rules file must be a JSON array")
        report = {"total_rules": len(rules), "citable": 0, "candidate_only": 0, "missing_evidence": 0, "details": []}
        for rule in rules:
            rule_id = rule.get("id", "<unknown>")
            evidence = rule.get("evidence")
            if not evidence:
                report["missing_evidence"] += 1
                report["details"].append({"rule_id": rule_id, "status": "missing_evidence"})
                continue
            resolved = resolve_evidence(evidence, kb_root or settings.kb_sources_root)
            citable = is_citable_evidence(resolved)
            status = "citable" if citable else "candidate_only"
            if citable:
                report["citable"] += 1
            else:
                report["candidate_only"] += 1
            report["details"].append({"rule_id": rule_id, "status": status})
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


    @app.command("eval-corpus")
    def eval_corpus(
        eval_path: Path = typer.Option(Path("eval/corpus_eval_cases.yaml"), "--eval-path"),
        collection: str | None = typer.Option(None, "--collection"),
        top_k: int | None = typer.Option(None, "--top-k"),
        base_url: str | None = typer.Option(None, "--base-url"),
        api_key: str | None = typer.Option(None, "--api-key"),
    ):
        retriever = KBSearchRetriever(base_url=base_url, api_key=api_key)
        out = run_corpus_eval(eval_path=eval_path, retriever=retriever, collection=collection, top_k=top_k)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("match-rule")
    def match_rule(
        event: Path = typer.Option(..., "--event"),
        rules_path: Path = typer.Option(Path("data/processed/corpus/sample_rules.json"), "--rules-path"),
        kb_root: Path | None = typer.Option(None, "--kb-root"),
    ):
        out = run_match_rule(event_path=event, rules_path=rules_path, kb_root=kb_root)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))



def _main_fallback():  # pragma: no cover
    parser = argparse.ArgumentParser(description="Chinese astro model CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate-data")

    p_inspect = sub.add_parser("inspect-kb")
    p_inspect.add_argument("--root")
    p_inspect.add_argument("--query")
    p_inspect.add_argument("--book-id")
    p_inspect.add_argument("--card-type", action="append")
    p_inspect.add_argument("--evidence-level")
    p_inspect.add_argument("--limit", type=int, default=None)
    p_inspect.add_argument("--collection")
    p_inspect.add_argument("--base-url")
    p_inspect.add_argument("--api-key")
    p_inspect.add_argument("--show-related", action="store_true")
    p_inspect.add_argument("--show-raw", action="store_true")

    p_resolve = sub.add_parser("resolve-evidence")
    p_resolve.add_argument("--rule", required=True)
    p_resolve.add_argument("--kb-root")
    p_resolve.add_argument("--pretty", action="store_true")
    p_resolve.add_argument("--strict", action="store_true")
    p_eval = sub.add_parser("eval-corpus")
    p_eval.add_argument("--eval-path", default="eval/corpus_eval_cases.yaml")
    p_eval.add_argument("--collection")
    p_eval.add_argument("--top-k", type=int, default=None)
    p_eval.add_argument("--base-url")
    p_eval.add_argument("--api-key")
    p_match = sub.add_parser("match-rule")
    p_match.add_argument("--event", required=True)
    p_match.add_argument("--rules-path", default="data/processed/corpus/sample_rules.json")
    p_match.add_argument("--kb-root")

    args = parser.parse_args()
    if args.cmd == "validate-data":
        out = validate_data_impl()
        print(f"Validation passed: {out['rules']} rules, {out['asterisms']} asterisms")
    elif args.cmd == "inspect-kb":
        out = inspect_kb_impl(
            Path(args.root) if args.root else None,
            args.query,
            args.book_id,
            args.card_type,
            args.evidence_level,
            args.limit,
            args.show_raw,
            args.base_url,
            args.api_key,
            args.collection,
            args.show_related,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "resolve-evidence":
        out = resolve_evidence_impl(Path(args.rule), Path(args.kb_root) if args.kb_root else None, args.strict)
        if args.pretty:
            print("\n".join(f"{k}: {v}" for k, v in out.items()))
            if out["status"] != "citable":
                print("当前仅为候选证据")
        else:
            print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "eval-corpus":
        retriever = KBSearchRetriever(base_url=args.base_url, api_key=args.api_key)
        out = run_corpus_eval(eval_path=Path(args.eval_path), retriever=retriever, collection=args.collection, top_k=args.top_k)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "match-rule":
        out = run_match_rule(event_path=Path(args.event), rules_path=Path(args.rules_path), kb_root=Path(args.kb_root) if args.kb_root else None)
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if typer:
        app()
    else:
        _main_fallback()

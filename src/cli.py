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

from src.connectors.evidence_resolver import resolve_evidence
from src.connectors.kb_contract import STAGE1_RECALL_CARD_TYPES, STAGE2_PRIMARY_CARD_TYPES
from src.connectors.kb_search_retriever import KBSearchRetriever
from src.connectors.manifest_reader import ManifestReader

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


def _split_hits(result: dict[str, Any]) -> dict[str, Any]:
    hits = result.get("hits", [])
    structured = [h for h in hits if h.get("card_type") in [c.value for c in STAGE1_RECALL_CARD_TYPES]]
    primary = [h for h in hits if h.get("card_type") in [c.value for c in STAGE2_PRIMARY_CARD_TYPES]]
    return {"hits": hits, "structured_hits": structured, "primary_hits": primary}


def inspect_kb_impl(
    root: Path | None = None,
    query: str | None = None,
    book_id: str | None = None,
    card_type: list[str] | None = None,
    evidence_level: str | None = None,
    limit: int = 20,
    show_raw: bool = False,
):
    if query:
        retriever = KBSearchRetriever()
        try:
            stage = retriever.two_stage_retrieve(query, book_id=book_id, limit=limit)
        except Exception as exc:
            return {
                "mode": "search",
                "query": query,
                "root": str(root) if root else None,
                "error": str(exc),
                "hint": "check KB_SEARCH_API_KEY, KB_SEARCH_API_PORT, and whether kb-search service is running",
            }
        out = {
            "mode": "search",
            "query": query,
            "root": str(root) if root else None,
            "stage1": _split_hits(stage.get("stage1", {})),
            "stage2": _split_hits(stage.get("stage2", {})),
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
    rule_obj = _load_json(rule)
    if isinstance(rule_obj, list):
        if not rule_obj:
            raise ValueError("rule file is an empty array")
        rule_obj = rule_obj[0]

    evidence = rule_obj.get("evidence")
    if not evidence:
        raise ValueError("rule file has no evidence")

    resolved = resolve_evidence(evidence, kb_root)
    payload = {
        "rule_id": rule_obj.get("id"),
        "kb_book_id": resolved.get("kb_book_id"),
        "note_id": resolved.get("note_id"),
        "relative_path": resolved.get("relative_path"),
        "card_type": resolved.get("card_type"),
        "locator": resolved.get("locator"),
        "anchor_heading": resolved.get("anchor_heading"),
        "quote": resolved.get("quote"),
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
        limit: int = typer.Option(20, "--limit"),
        show_raw: bool = typer.Option(False, "--show-raw"),
    ):
        out = inspect_kb_impl(root, query, book_id, card_type, evidence_level, limit, show_raw)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("resolve-evidence")
    def resolve_evidence_cmd(
        rule: Path = typer.Option(..., "--rule"),
        kb_root: Path | None = typer.Option(None, "--kb-root"),
        show_json: bool = typer.Option(False, "--show-json"),
        strict: bool = typer.Option(False, "--strict"),
    ):
        out = resolve_evidence_impl(rule, kb_root=kb_root, strict=strict)
        if show_json:
            typer.echo(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            typer.echo("\n".join(f"{k}: {v}" for k, v in out.items()))
            if out["status"] != "citable":
                typer.echo("当前仅为候选证据")


    @app.command("search-kb")
    def search_kb(query: str, book_id: str | None = None, card_type: list[str] | None = None, evidence_level: str | None = None, limit: int = 20):
        retriever = KBSearchRetriever()
        result = retriever.search(query, book_id=book_id, card_types=card_type, evidence_level=evidence_level, limit=limit)
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


    @app.command("audit-rules")
    def audit_rules(rules_path: Path = Path("data/processed/corpus/sample_rules.json"), kb_root: Path | None = None):
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
            resolved = resolve_evidence(evidence, kb_root)
            status = resolved.get("status", "unknown")
            if status == "citable":
                report["citable"] += 1
            else:
                report["candidate_only"] += 1
            report["details"].append({"rule_id": rule_id, "status": str(status)})
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))



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
    p_inspect.add_argument("--limit", type=int, default=20)
    p_inspect.add_argument("--show-raw", action="store_true")

    p_resolve = sub.add_parser("resolve-evidence")
    p_resolve.add_argument("--rule", required=True)
    p_resolve.add_argument("--kb-root")
    p_resolve.add_argument("--show-json", action="store_true")
    p_resolve.add_argument("--strict", action="store_true")

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
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "resolve-evidence":
        out = resolve_evidence_impl(Path(args.rule), Path(args.kb_root) if args.kb_root else None, args.strict)
        if args.show_json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print("\n".join(f"{k}: {v}" for k, v in out.items()))
            if out["status"] != "citable":
                print("当前仅为候选证据")


if __name__ == "__main__":
    if typer:
        app()
    else:
        _main_fallback()

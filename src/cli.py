from __future__ import annotations

import json
from pathlib import Path

import typer
from jsonschema import validate

from src.connectors.evidence_resolver import resolve_evidence
from src.connectors.kb_search_retriever import KBSearchRetriever
from src.connectors.manifest_reader import ManifestReader

app = typer.Typer(help="Chinese astro model CLI")


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@app.command("validate-data")
def validate_data(
    rules_path: Path = Path("data/processed/corpus/sample_rules.json"),
    asterism_path: Path = Path("data/processed/ontology/sample_asterisms.json"),
    rule_schema: Path = Path("schemas/omen_rule.schema.json"),
    asterism_schema: Path = Path("schemas/asterism.schema.json"),
):
    rules = _load_json(rules_path)
    rule_schema_obj = _load_json(rule_schema)
    for idx, rule in enumerate(rules):
        validate(instance=rule, schema=rule_schema_obj)
    asterisms = _load_json(asterism_path)
    asterism_schema_obj = _load_json(asterism_schema)
    for idx, item in enumerate(asterisms):
        validate(instance=item, schema=asterism_schema_obj)
    typer.echo(f"Validation passed: {len(rules)} rules, {len(asterisms)} asterisms")


@app.command("inspect-kb")
def inspect_kb(root: Path):
    reader = ManifestReader(root)
    typer.echo(json.dumps(reader.inspect(), ensure_ascii=False, indent=2))


@app.command("resolve-evidence")
def resolve_evidence_cmd(rule: Path, kb_root: Path | None = None):
    rule_obj = _load_json(rule)
    evidence = rule_obj.get("evidence")
    if not evidence:
        raise typer.BadParameter("rule file has no evidence")
    resolved = resolve_evidence(evidence, kb_root)
    typer.echo(json.dumps(resolved, ensure_ascii=False, indent=2))


@app.command("search-kb")
def search_kb(
    query: str,
    book_id: str | None = None,
    card_type: list[str] | None = None,
    evidence_level: str | None = None,
    limit: int = 20,
):
    retriever = KBSearchRetriever()
    result = retriever.search(
        query,
        book_id=book_id,
        card_types=card_type,
        evidence_level=evidence_level,
        limit=limit,
    )
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("audit-rules")
def audit_rules(
    rules_path: Path = Path("data/processed/corpus/sample_rules.json"),
    kb_root: Path | None = None,
):
    rules = _load_json(rules_path)
    if not isinstance(rules, list):
        raise typer.BadParameter("rules file must be a JSON array")

    citable = 0
    candidate_only = 0
    missing_evidence = 0
    details: list[dict[str, str]] = []

    for rule in rules:
        rule_id = rule.get("id", "<unknown>")
        evidence = rule.get("evidence")
        if not evidence:
            missing_evidence += 1
            details.append({"rule_id": rule_id, "status": "missing_evidence"})
            continue
        resolved = resolve_evidence(evidence, kb_root)
        status = resolved.get("status", "unknown")
        if status == "citable":
            citable += 1
        elif status == "candidate_only":
            candidate_only += 1
        details.append({"rule_id": rule_id, "status": str(status)})

    report = {
        "total_rules": len(rules),
        "citable": citable,
        "candidate_only": candidate_only,
        "missing_evidence": missing_evidence,
        "details": details,
    }
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()

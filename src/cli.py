from __future__ import annotations

import json
from pathlib import Path

import typer
from jsonschema import validate

from src.connectors.evidence_resolver import resolve_evidence
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


if __name__ == "__main__":
    app()

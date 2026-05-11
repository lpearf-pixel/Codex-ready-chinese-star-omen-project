from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
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
from src.eval.corpus_eval import load_eval_cases, run_corpus_eval
from src.eval.historical_benchmark import export_benchmark_markdown, load_benchmark_case, run_benchmark_case
from src.calibration.error_analysis import analyze_errors, write_error_outputs
from src.calibration.experiment_runner import create_calibration_snapshot, run_calibration_experiment
from src.calibration.profile_compare_report import build_profile_compare_report, profile_compare_markdown
from src.calibration.profile_registry import promote_profile, propose_profile, rollback_profile
from src.calibration.profile_runner import run_profile_compare
from src.calibration.profile_stability import analyze_profile_stability
from src.calibration.review_analysis import analyze_review_data
from src.calibration.rule_leaderboard import build_rule_leaderboard, leaderboard_to_markdown
from src.calibration.tuning_recommendations import generate_tuning_recommendations, tuning_to_markdown
from src.pipeline.batch_runner import run_batch
from src.research.templates import render_layered_template
from src.astronomy import MinimalAsterismMatcher, MinimalCelestialEventDetector, MinimalWindowScanner, SkyfieldEphemerisProvider, cluster_events
from src.review.review_queue import (
    DEFAULT_QUEUE_PATH,
    DEFAULT_REVIEWED_PATH,
    build_review_queue_from_benchmark,
    export_review_markdown,
    load_jsonl,
    update_review_item,
)
from src.rule_engine.minimal_matcher import load_json, match_event_to_rules, run_match_rule

app = typer.Typer(help="Chinese astro model CLI") if typer else None


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _enrich_events_with_match_context(
    events: list[dict[str, Any]],
    *,
    points: list[dict[str, Any]],
    matches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    point_map = {str(p.get("body")): p for p in points if p.get("body")}
    enriched: list[dict[str, Any]] = []
    for event in events:
        body = str(event.get("body") or "")
        target = str(event.get("target_asterism") or "")
        point = point_map.get(body, {})
        event_match = next((m for m in matches if m.get("body") == body and m.get("matched_asterism_id") == target), {})
        enriched.append(
            {
                **event,
                "calc_source": event.get("calc_source") or point.get("calc_source"),
                "calc_quality": event.get("calc_quality") or point.get("calc_quality"),
                "ephemeris_provider": event.get("ephemeris_provider") or point.get("ephemeris_provider"),
                "is_visible": ((event.get("visibility") or {}).get("is_visible") if isinstance(event.get("visibility"), dict) else None),
                "visibility_reason": ((event.get("visibility") or {}).get("visibility_reason") if isinstance(event.get("visibility"), dict) else None),
                "asterism_match_confidence": event_match.get("confidence"),
            }
        )
    return enriched


def run_detect_and_match_pipeline(
    *,
    datetime_utc: str,
    lon: float,
    lat: float,
    body: str,
    target: str,
    rules_path: Path,
    kb_root: Path | None,
    ephemeris_path: str | None,
    force_fallback: bool = False,
    cluster_window_days: int = 3,
    peak_selection_rule: str = "min_angular_distance",
) -> dict[str, Any]:
    provider = SkyfieldEphemerisProvider(ephemeris_path=ephemeris_path, force_fallback=force_fallback)
    matcher = MinimalAsterismMatcher()
    detector = MinimalCelestialEventDetector()
    points = provider.get_points(bodies=["moon", "mars", "jupiter", "saturn"], datetime_utc=datetime_utc, lon=lon, lat=lat)
    matches = matcher.match(points=points, targets=[target, "xin_xiu", "jiao_xiu", "fang_xiu"])
    events = detector.detect(datetime_utc=datetime_utc, lon=lon, lat=lat, body=body, target=target, points=points, matches=matches)
    enriched_events = _enrich_events_with_match_context(events, points=points, matches=matches)
    clustering = cluster_events(enriched_events, window_days=cluster_window_days, peak_selection_rule=peak_selection_rule)
    rules = load_json(rules_path)
    rule_matches = [match_event_to_rules(event=ev, rules=rules, kb_root=kb_root) for ev in clustering["events"]]
    first_event = clustering["events"][0] if clustering["events"] else {}
    first_match = rule_matches[0] if rule_matches else {}
    return {
        "input": {"datetime": datetime_utc, "lon": lon, "lat": lat, "body": body, "target": target},
        "points": points,
        "asterism_matches": matches,
        "detected_events": enriched_events,
        "clustered_events": clustering["events"],
        "event_clusters": clustering["clusters"],
        "rule_matches": rule_matches,
        "calc_source": first_event.get("calc_source"),
        "calc_quality": first_event.get("calc_quality"),
        "ephemeris_provider": first_event.get("ephemeris_provider"),
        "is_visible": first_event.get("is_visible"),
        "visibility_reason": first_event.get("visibility_reason"),
        "asterism_match_confidence": first_event.get("asterism_match_confidence"),
        "event_cluster_id": first_event.get("event_cluster_id"),
        "matched_rule_ids": first_match.get("matched_rule_ids", []),
        "match_status": first_match.get("match_status", "not_matched"),
        "match_score": first_match.get("match_score", 0.0),
        "primary_evidence_found": first_match.get("primary_evidence_found", False),
        "candidate_only": first_match.get("candidate_only", True),
    }


def replay_event_impl(
    *,
    case_path: Path,
    rules_path: Path = Path("data/processed/corpus/sample_rules.json"),
    kb_root: Path | None = None,
    ephemeris_path: str | None = None,
) -> dict[str, Any]:
    case = _load_json(case_path)
    output = run_detect_and_match_pipeline(
        datetime_utc=str(case["input_datetime_utc"]),
        lon=float(case["location"]["lon"]),
        lat=float(case["location"]["lat"]),
        body=str(case.get("body") or "mars"),
        target=str(case.get("target") or "xin_xiu"),
        rules_path=rules_path,
        kb_root=kb_root,
        ephemeris_path=ephemeris_path,
        force_fallback=bool(case.get("force_fallback", False)),
        cluster_window_days=int(case.get("event_cluster_window_days", 3)),
        peak_selection_rule=str(case.get("peak_selection_rule", "min_angular_distance")),
    )
    first_point = next((p for p in output["points"] if p.get("body") == case.get("body")), output["points"][0] if output["points"] else {})
    first_match = output["rule_matches"][0] if output["rule_matches"] else {}
    return {
        "input_case_id": case.get("case_id"),
        "input_datetime_utc": case.get("input_datetime_utc"),
        "location": case.get("location"),
        "calc_source": first_point.get("calc_source"),
        "calc_quality": first_point.get("calc_quality"),
        "generated_events": output["detected_events"],
        "clustered_events": output["clustered_events"],
        "matched_rule_ids": first_match.get("matched_rule_ids", []),
        "match_status": first_match.get("match_status", "not_matched"),
        "match_score": first_match.get("match_score", 0.0),
        "evidence_summary": first_match.get("evidence_summary", {}),
        "primary_evidence_found": first_match.get("primary_evidence_found", False),
        "candidate_only": first_match.get("candidate_only", True),
        "event_clusters": output["event_clusters"],
        "rule_matches": output["rule_matches"],
    }


def scan_window_impl(
    *,
    start_datetime_utc: str,
    end_datetime_utc: str,
    lon: float,
    lat: float,
    bodies: list[str],
    targets: list[str],
    event_types: list[str],
    rules_path: Path = Path("data/processed/corpus/sample_rules.json"),
    kb_root: Path | None = None,
    ephemeris_path: str | None = None,
    force_fallback: bool = False,
    cluster_window_days: int = 3,
    peak_selection_rule: str = "min_angular_distance",
    step_hours: int = 24,
) -> dict[str, Any]:
    scanner = MinimalWindowScanner(
        ephemeris_path=ephemeris_path,
        force_fallback=force_fallback,
        cluster_window_days=cluster_window_days,
        peak_selection_rule=peak_selection_rule,
    )
    return scanner.scan(
        start_datetime_utc=start_datetime_utc,
        end_datetime_utc=end_datetime_utc,
        lon=lon,
        lat=lat,
        bodies=bodies,
        targets=targets,
        event_types=event_types,
        rules_path=rules_path,
        kb_root=kb_root,
        step_hours=step_hours,
    )


def benchmark_window_impl(
    *,
    case_path: Path,
    rules_path: Path = Path("data/processed/corpus/sample_rules.json"),
    ephemeris_path: str | None = None,
    force_fallback: bool = False,
) -> dict[str, Any]:
    case = load_benchmark_case(case_path)
    return run_benchmark_case(
        case=case,
        rules_path=rules_path,
        ephemeris_path=ephemeris_path,
        force_fallback=force_fallback,
    )


def build_review_queue_impl(
    *,
    benchmark_path: Path,
    queue_path: Path = DEFAULT_QUEUE_PATH,
) -> dict[str, Any]:
    payload = _load_json(benchmark_path)
    return build_review_queue_from_benchmark(payload, queue_path=queue_path)


def review_item_impl(
    *,
    review_item_id: str,
    status: str,
    notes: str,
    queue_path: Path = DEFAULT_QUEUE_PATH,
    reviewed_path: Path = DEFAULT_REVIEWED_PATH,
) -> dict[str, Any]:
    return update_review_item(
        review_item_id=review_item_id,
        status=status,
        notes=notes,
        queue_path=queue_path,
        reviewed_path=reviewed_path,
    )


def export_review_impl(
    *,
    benchmark_path: Path | None,
    queue_path: Path = DEFAULT_QUEUE_PATH,
    out_path: Path | None = None,
    format: str = "md",
) -> dict[str, Any]:
    if format != "md":
        raise ValueError("only md export is supported in Sprint 9 minimal implementation")
    queue_rows = load_jsonl(queue_path)
    benchmark_payloads: list[dict[str, Any]] = []
    if benchmark_path and benchmark_path.exists():
        benchmark_payloads = [_load_json(benchmark_path)]
    text = export_review_markdown(queue_rows=queue_rows, benchmark_payloads=benchmark_payloads)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    return {
        "ok": True,
        "format": "md",
        "queue_item_count": len(queue_rows),
        "out_path": str(out_path) if out_path else None,
        "content": text if not out_path else None,
    }


def analyze_reviews_impl(
    *,
    review_queue: Path = DEFAULT_QUEUE_PATH,
    reviewed: Path = DEFAULT_REVIEWED_PATH,
    benchmark_json: Path | None = None,
) -> dict[str, Any]:
    benchmark_rows = [_load_json(benchmark_json)] if benchmark_json and benchmark_json.exists() else None
    return analyze_review_data(
        review_queue_path=review_queue,
        reviewed_path=reviewed,
        benchmark_rows=benchmark_rows,
    )


def compare_thresholds_impl(
    *,
    cases_path: Path,
    profiles: list[str],
    profile_config: Path = Path("config/event_threshold_profiles.yaml"),
) -> dict[str, Any]:
    return run_profile_compare(cases_path=cases_path, profiles_path=profile_config, profile_names=profiles)


def error_analysis_impl(*, compare_payload: dict[str, Any], out_dir: Path | None = None) -> dict[str, Any]:
    payload = analyze_errors(compare_payload)
    out_files = write_error_outputs(payload, out_dir=out_dir) if out_dir else {}
    return {"analysis": payload, "output_files": out_files}


def rule_leaderboard_impl(
    *,
    reviewed_path: Path = DEFAULT_REVIEWED_PATH,
    format: str = "json",
    out_path: Path | None = None,
) -> dict[str, Any]:
    rows = load_jsonl(reviewed_path)
    leaderboard = build_rule_leaderboard(rows)
    if format == "md":
        content = leaderboard_to_markdown(leaderboard)
        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
        return {"format": "md", "rows": leaderboard, "content": content if not out_path else None, "out_path": str(out_path) if out_path else None}
    return {"format": "json", "rows": leaderboard}


def tuning_report_impl(
    *,
    compare_payload: dict[str, Any],
    review_analysis_payload: dict[str, Any],
    leaderboard_payload: list[dict[str, Any]],
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> dict[str, Any]:
    payload = generate_tuning_recommendations(
        review_analysis=review_analysis_payload,
        profile_compare=compare_payload,
        rule_leaderboard=leaderboard_payload,
    )
    md = tuning_to_markdown(payload)
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if out_md:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(md, encoding="utf-8")
    return {
        "report": payload,
        "markdown": md if not out_md else None,
        "out_json": str(out_json) if out_json else None,
        "out_md": str(out_md) if out_md else None,
    }


def run_calibration_experiment_impl(*, profile: str, cases: Path, review_source: Path = DEFAULT_REVIEWED_PATH) -> dict[str, Any]:
    return run_calibration_experiment(profile_name=profile, cases_path=cases, review_source=review_source)


def run_batch_impl(*, cases: Path, profiles: list[str]) -> dict[str, Any]:
    return run_batch(cases_dir=cases, profiles=profiles)


def export_batch_index_impl(*, run_id: str, format: str = "json") -> dict[str, Any]:
    run_dir = Path("data/runs") / run_id
    if format == "md":
        return {"run_id": run_id, "format": "md", "content": (run_dir / "report_index.md").read_text(encoding="utf-8")}
    return {"run_id": run_id, "format": "json", "content": _load_json(run_dir / "report_index.json")}


def profile_stability_impl(*, profile: str) -> dict[str, Any]:
    return analyze_profile_stability(profile_name=profile)


def export_layered_report_impl(*, run_id: str, level: str) -> dict[str, Any]:
    run_dir = Path("data/runs") / run_id
    rows = _load_json(run_dir / "results.json")
    selected = [r for r in rows if r.get("output_level") == level]
    out_dir = run_dir / "layered_reports" / level
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for row in selected:
        name = f"{row.get('case_id')}.md"
        text = render_layered_template(level=level, row=row)
        p = out_dir / name
        p.write_text(text, encoding="utf-8")
        files.append(str(p))
    return {"run_id": run_id, "level": level, "count": len(files), "files": files}


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
        "matched_quotes": result.get("matched_quotes", []),
    }
    if "debug_scan" in result:
        payload["debug_scan"] = result["debug_scan"]
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
    query_mode: str | None = None,
    literal_first: bool | None = None,
):
    settings = get_settings()
    effective_limit = limit if limit is not None else settings.app_default_limit
    if query:
        if query_mode is None and query in KBSearchRetriever.PRIMARY_ONLY_PHRASES:
            query_mode = "evidence"
        if literal_first is None and query_mode == "evidence":
            literal_first = True
        retriever = KBSearchRetriever(base_url=base_url, api_key=api_key)
        filters: dict[str, Any] = {}
        if book_id:
            filters["kb_book_id"] = book_id
        if card_type:
            filters["card_type"] = card_type
        if evidence_level:
            filters["evidence_level"] = evidence_level
        try:
            stage = retriever.two_stage_retrieve(
                query,
                top_k=effective_limit,
                limit=effective_limit,
                collection=collection,
                filters=filters or None,
                query_mode=query_mode,
                literal_first=literal_first,
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



def _safe_candidate_filename(candidate_id: str) -> str:
    digest = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16]
    return f"candidate-{digest}.md"


def _frontmatter_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _write_candidate_markdown(path: Path, frontmatter: dict[str, Any], body: str) -> None:
    lines = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {_frontmatter_value(value)}")
    lines.extend(["---", "", body.rstrip(), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _empty_candidate_manifest(*, base_corpus_version: str | None = None, base_ingest_run_id: str | None = None) -> dict[str, Any]:
    return {
        "base_corpus_version": base_corpus_version,
        "base_ingest_run_id": base_ingest_run_id,
        "current_upstream_corpus_version": base_corpus_version,
        "last_synced_at": None,
        "items": [],
    }


def _load_candidate_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_candidate_manifest()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        manifest = _empty_candidate_manifest()
        manifest["items"] = loaded
        return manifest
    if not isinstance(loaded, dict):
        return _empty_candidate_manifest()
    if "items" not in loaded:
        loaded["items"] = loaded.get("candidates", []) if isinstance(loaded.get("candidates"), list) else []
    loaded.setdefault("base_corpus_version", None)
    loaded.setdefault("base_ingest_run_id", None)
    loaded.setdefault("current_upstream_corpus_version", loaded.get("base_corpus_version"))
    loaded.setdefault("last_synced_at", None)
    return loaded


def _write_candidate_manifest(path: Path, manifest: dict[str, Any]) -> None:
    manifest = {**manifest, "items": sorted(manifest.get("items", []), key=lambda item: item.get("id", ""))}
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_upstream_version(meta: dict[str, Any]) -> tuple[str | None, str | None]:
    corpus_version = meta.get("corpus_version") or meta.get("version") or meta.get("kb_corpus_version")
    ingest_run_id = meta.get("ingest_run_id") or meta.get("run_id") or meta.get("last_ingest_run_id")
    return (str(corpus_version) if corpus_version is not None else None, str(ingest_run_id) if ingest_run_id is not None else None)


def _clear_downstream_query_cache() -> list[str]:
    cleared: list[str] = []
    for path in [Path("data/cache/kb_queries"), Path("data/generated_candidates/.query_cache")]:
        if path.exists():
            shutil.rmtree(path)
            cleared.append(str(path))
    return cleared


def _compact_for_compare(text: str) -> str:
    return "".join(ch for ch in str(text) if not ch.isspace())


def generate_candidate_card_impl(
    query: str,
    book_id: str,
    out_dir: Path,
    *,
    limit: int | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    generated_root = Path("data/generated_candidates").resolve()
    resolved_out_dir = out_dir.resolve()
    if generated_root != resolved_out_dir and generated_root not in resolved_out_dir.parents:
        raise ValueError("candidate cards must be written under data/generated_candidates")

    settings = get_settings()
    effective_limit = limit if limit is not None else settings.app_default_limit
    retriever = KBSearchRetriever(base_url=base_url, api_key=api_key)
    query_variants = retriever._query_variants(query)
    hits, scan_meta = retriever._scan_primary_files(
        query,
        book_id=book_id,
        mode="evidence",
        limit=effective_limit,
        query_variants=query_variants,
    )
    selected_hits = [h for h in hits if h.get("match_type") == "exact_phrase" and h.get("card_type") == "fenjuan"]
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "candidate_manifest.json"
    manifest_doc = _load_candidate_manifest(manifest_path)
    by_id = {str(item.get("id")): item for item in manifest_doc.get("items", []) if item.get("id")}
    generated: list[dict[str, Any]] = []
    for hit in selected_hits:
        normalized_term = KBSearchRetriever._normalize_query(query)
        source_volume = str(hit.get("title") or "")
        source_locator = str(hit.get("source_locator") or source_volume or Path(str(hit.get("path") or "")).stem)
        match_offset = hit.get("match_offset")
        candidate_id = f"{book_id}:{normalized_term}:{source_locator}:{match_offset}"
        anchor_text = str(hit.get("excerpt") or hit.get("snippet") or "")
        content_hash = hashlib.sha256("\n".join([candidate_id, anchor_text]).encode("utf-8")).hexdigest()
        heading_path = hit.get("heading_path") if isinstance(hit.get("heading_path"), list) else [source_volume]
        frontmatter = {
            "id": candidate_id,
            "kb_book_id": book_id,
            "book_title": hit.get("book_title") or "唐開元占經",
            "card_type": "extract_card",
            "evidence_level": "candidate",
            "generated_status": "candidate",
            "generated_by": "codex_ready_filesystem_fallback",
            "review_status": "pending",
            "source_namespace": "downstream_generated",
            "term": query,
            "aliases": query_variants,
            "source_file": hit.get("path"),
            "source_locator": source_locator,
            "source_volume": source_volume,
            "page_marker": None,
            "heading_path": heading_path,
            "paragraph_index": None,
            "match_type": hit.get("match_type"),
            "match_offset": match_offset,
            "anchor_text": anchor_text,
            "content_hash": content_hash,
        }
        body = f"# {query}\n\n> {anchor_text}\n\n候选证据卡由 downstream filesystem fallback 生成，等待人工 review 后再进入正式 KB ingest。"
        filename = _safe_candidate_filename(candidate_id)
        card_path = out_dir / filename
        _write_candidate_markdown(card_path, frontmatter, body)
        manifest_item = {
            "id": candidate_id,
            "path": str(card_path),
            "kb_book_id": book_id,
            "term": query,
            "source_file": hit.get("path"),
            "source_locator": source_locator,
            "match_offset": match_offset,
            "review_status": "pending",
            "sync_status": "pending",
            "content_hash": content_hash,
            "anchor_text": anchor_text,
        }
        by_id[candidate_id] = manifest_item
        generated.append(manifest_item)

    if manifest_doc.get("base_corpus_version") is None:
        manifest_doc["base_corpus_version"] = manifest_doc.get("current_upstream_corpus_version")
    manifest_doc["items"] = list(by_id.values())
    _write_candidate_manifest(manifest_path, manifest_doc)
    return {
        "mode": "generate_candidate_card",
        "query": query,
        "book_id": book_id,
        "out_dir": str(out_dir),
        "generated_count": len(generated),
        "generated": generated,
        "manifest_path": str(manifest_path),
        "files_scanned": scan_meta.get("files_scanned", 0),
        "matched_headings": scan_meta.get("matched_headings", []),
    }


def sync_upstream_status_impl(
    book_id: str,
    candidate_root: Path,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    retriever = KBSearchRetriever(base_url=base_url, api_key=api_key)
    try:
        upstream_meta = retriever.upstream_meta()
    except Exception as exc:
        return {
            "mode": "sync_upstream_status",
            "book_id": book_id,
            "candidate_root": str(candidate_root),
            "error": str(exc),
            "hint": "check KB_SEARCH_BASE_URL/KB_SEARCH_API_PORT and whether upstream kb-search service is running; sync does not call ingest",
        }
    corpus_version, ingest_run_id = _extract_upstream_version(upstream_meta)
    synced_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    cleared_cache: list[str] = []
    manifests: list[dict[str, Any]] = []

    for manifest_path in candidate_root.rglob("candidate_manifest.json"):
        manifest = _load_candidate_manifest(manifest_path)
        previous_version = manifest.get("current_upstream_corpus_version")
        if corpus_version and previous_version and previous_version != corpus_version:
            cleared_cache.extend(_clear_downstream_query_cache())
        manifest.setdefault("base_corpus_version", corpus_version)
        manifest.setdefault("base_ingest_run_id", ingest_run_id)
        manifest["current_upstream_corpus_version"] = corpus_version
        manifest["last_synced_at"] = synced_at
        changed = 0
        counts = {"pending": 0, "merged": 0, "needs_review": 0, "stale": 0}
        for item in manifest.get("items", []):
            if not isinstance(item, dict):
                continue
            if book_id and item.get("kb_book_id") != book_id:
                continue
            old_status = item.get("sync_status", "pending")
            source_file = item.get("source_file")
            if source_file and not Path(str(source_file)).exists():
                item["sync_status"] = "stale"
            else:
                term = str(item.get("term") or "")
                source_locator = str(item.get("source_locator") or "")
                anchor_text = str(item.get("anchor_text") or "")
                content_hash = str(item.get("content_hash") or "")
                query = " ".join(part for part in [term, source_locator, anchor_text[:120]] if part)
                try:
                    result = retriever.retrieve(
                        query or term,
                        top_k=top_k,
                        filters={"kb_book_id": item.get("kb_book_id") or book_id},
                        query_mode="evidence",
                        literal_first=True,
                    )
                except Exception:
                    result = {"hits": [], "exact_hits": [], "related_hits": []}
                hits = result.get("hits", []) + result.get("exact_hits", []) + result.get("related_hits", [])
                compact_anchor = _compact_for_compare(anchor_text)
                merged = False
                term_hit = False
                for hit in hits:
                    hit_text = "\n".join(str(hit.get(k) or "") for k in ("content_hash", "anchor_text", "excerpt", "snippet", "title", "source_locator"))
                    if content_hash and content_hash in hit_text:
                        merged = True
                        break
                    compact_hit = _compact_for_compare(hit_text)
                    if compact_anchor and (compact_anchor in compact_hit or compact_hit in compact_anchor):
                        merged = True
                        break
                    if term and _compact_for_compare(term) in compact_hit:
                        term_hit = True
                if merged:
                    item["sync_status"] = "merged"
                elif term_hit:
                    item["sync_status"] = "needs_review"
                else:
                    item["sync_status"] = "pending"
            item["last_synced_at"] = synced_at
            item["current_upstream_corpus_version"] = corpus_version
            if item.get("sync_status") != old_status:
                changed += 1
            status = str(item.get("sync_status") or "pending")
            counts[status] = counts.get(status, 0) + 1
        _write_candidate_manifest(manifest_path, manifest)
        manifests.append({"path": str(manifest_path), "changed": changed, "counts": counts})
    return {
        "mode": "sync_upstream_status",
        "book_id": book_id,
        "candidate_root": str(candidate_root),
        "current_upstream_corpus_version": corpus_version,
        "base_ingest_run_id": ingest_run_id,
        "last_synced_at": synced_at,
        "manifests": manifests,
        "cleared_cache": sorted(set(cleared_cache)),
    }

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
        query_mode: str | None = typer.Option(None, "--query-mode"),
        literal_first: bool | None = typer.Option(None, "--literal-first"),
    ):
        out = inspect_kb_impl(root, query, book_id, card_type, evidence_level, limit, show_raw, base_url, api_key, collection, show_related, query_mode, literal_first)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))




    @app.command("sync-upstream-status")
    def sync_upstream_status(
        book_id: str = typer.Option(..., "--book-id"),
        candidate_root: Path = typer.Option(Path("data/generated_candidates"), "--candidate-root"),
        base_url: str | None = typer.Option(None, "--base-url"),
        api_key: str | None = typer.Option(None, "--api-key"),
    ):
        out = sync_upstream_status_impl(book_id, candidate_root, base_url=base_url, api_key=api_key)
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
            filters["kb_book_id"] = book_id
        if card_type:
            filters["card_type"] = card_type
        if evidence_level:
            filters["evidence_level"] = evidence_level
        try:
            result = retriever.search(
                query,
                top_k=top_k,
                limit=top_k,
                collection=collection,
                filters=filters or None,
                query_mode=query_mode,
                literal_first=literal_first,
                literal_pool_factor=literal_pool_factor,
            )
        except Exception as exc:
            result = {
                "mode": "search",
                "query": query,
                "error": str(exc),
                "hint": "check KB_SEARCH_API_KEY and kb-search service",
            }
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


    @app.command("generate-candidate-card")
    def generate_candidate_card(
        query: str = typer.Option(..., "--query"),
        book_id: str = typer.Option(..., "--book-id"),
        out_dir: Path = typer.Option(..., "--out-dir"),
        limit: int | None = typer.Option(None, "--limit"),
        base_url: str | None = typer.Option(None, "--base-url"),
        api_key: str | None = typer.Option(None, "--api-key"),
    ):
        out = generate_candidate_card_impl(query, book_id, out_dir, limit=limit, base_url=base_url, api_key=api_key)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


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


    @app.command("detect-and-match")
    def detect_and_match(
        datetime: str = typer.Option(..., "--datetime"),
        lon: float = typer.Option(..., "--lon"),
        lat: float = typer.Option(..., "--lat"),
        body: str = typer.Option("mars", "--body"),
        target: str = typer.Option("xin_xiu", "--target"),
        rules_path: Path = typer.Option(Path("data/processed/corpus/sample_rules.json"), "--rules-path"),
        kb_root: Path | None = typer.Option(None, "--kb-root"),
        ephemeris_path: str | None = typer.Option(None, "--ephemeris-path"),
        force_fallback: bool = typer.Option(False, "--force-fallback"),
        cluster_window_days: int = typer.Option(3, "--cluster-window-days"),
        peak_selection_rule: str = typer.Option("min_angular_distance", "--peak-selection-rule"),
    ):
        out = run_detect_and_match_pipeline(
            datetime_utc=datetime,
            lon=lon,
            lat=lat,
            body=body,
            target=target,
            rules_path=rules_path,
            kb_root=kb_root,
            ephemeris_path=ephemeris_path,
            force_fallback=force_fallback,
            cluster_window_days=cluster_window_days,
            peak_selection_rule=peak_selection_rule,
        )
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("replay-event")
    def replay_event(
        case: Path = typer.Option(..., "--case"),
        rules_path: Path = typer.Option(Path("data/processed/corpus/sample_rules.json"), "--rules-path"),
        kb_root: Path | None = typer.Option(None, "--kb-root"),
        ephemeris_path: str | None = typer.Option(None, "--ephemeris-path"),
    ):
        out = replay_event_impl(case_path=case, rules_path=rules_path, kb_root=kb_root, ephemeris_path=ephemeris_path)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("scan-window")
    def scan_window(
        start: str = typer.Option(..., "--start"),
        end: str = typer.Option(..., "--end"),
        lon: float = typer.Option(..., "--lon"),
        lat: float = typer.Option(..., "--lat"),
        bodies: list[str] = typer.Option(["mars", "moon", "jupiter", "saturn"], "--bodies"),
        targets: list[str] = typer.Option(["xin_xiu", "jiao_xiu", "fang_xiu"], "--targets"),
        event_types: list[str] = typer.Option(["guarding", "invading", "conjunction", "gathering"], "--event-types"),
        rules_path: Path = typer.Option(Path("data/processed/corpus/sample_rules.json"), "--rules-path"),
        kb_root: Path | None = typer.Option(None, "--kb-root"),
        ephemeris_path: str | None = typer.Option(None, "--ephemeris-path"),
        force_fallback: bool = typer.Option(False, "--force-fallback"),
        cluster_window_days: int = typer.Option(3, "--cluster-window-days"),
        peak_selection_rule: str = typer.Option("min_angular_distance", "--peak-selection-rule"),
        step_hours: int = typer.Option(24, "--step-hours"),
    ):
        out = scan_window_impl(
            start_datetime_utc=start,
            end_datetime_utc=end,
            lon=lon,
            lat=lat,
            bodies=bodies,
            targets=targets,
            event_types=event_types,
            rules_path=rules_path,
            kb_root=kb_root,
            ephemeris_path=ephemeris_path,
            force_fallback=force_fallback,
            cluster_window_days=cluster_window_days,
            peak_selection_rule=peak_selection_rule,
            step_hours=step_hours,
        )
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("benchmark-window")
    def benchmark_window(
        case: Path = typer.Option(..., "--case"),
        rules_path: Path = typer.Option(Path("data/processed/corpus/sample_rules.json"), "--rules-path"),
        ephemeris_path: str | None = typer.Option(None, "--ephemeris-path"),
        force_fallback: bool = typer.Option(False, "--force-fallback"),
        export_md: Path | None = typer.Option(None, "--export-md"),
    ):
        out = benchmark_window_impl(
            case_path=case,
            rules_path=rules_path,
            ephemeris_path=ephemeris_path,
            force_fallback=force_fallback,
        )
        if export_md:
            export_md.parent.mkdir(parents=True, exist_ok=True)
            export_md.write_text(export_benchmark_markdown(out), encoding="utf-8")
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("build-review-queue")
    def build_review_queue_cmd(
        from_benchmark: Path = typer.Option(..., "--from-benchmark"),
        queue_path: Path = typer.Option(DEFAULT_QUEUE_PATH, "--queue-path"),
    ):
        out = build_review_queue_impl(benchmark_path=from_benchmark, queue_path=queue_path)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("review-item")
    def review_item_cmd(
        id: str = typer.Option(..., "--id"),
        status: str = typer.Option(..., "--status"),
        notes: str = typer.Option("", "--notes"),
        queue_path: Path = typer.Option(DEFAULT_QUEUE_PATH, "--queue-path"),
        reviewed_path: Path = typer.Option(DEFAULT_REVIEWED_PATH, "--reviewed-path"),
    ):
        out = review_item_impl(review_item_id=id, status=status, notes=notes, queue_path=queue_path, reviewed_path=reviewed_path)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("export-review")
    def export_review_cmd(
        format: str = typer.Option("md", "--format"),
        benchmark: Path | None = typer.Option(None, "--benchmark"),
        queue_path: Path = typer.Option(DEFAULT_QUEUE_PATH, "--queue-path"),
        out: Path | None = typer.Option(None, "--out"),
    ):
        payload = export_review_impl(benchmark_path=benchmark, queue_path=queue_path, out_path=out, format=format)
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


    @app.command("analyze-reviews")
    def analyze_reviews_cmd(
        review_queue: Path = typer.Option(DEFAULT_QUEUE_PATH, "--review-queue"),
        reviewed: Path = typer.Option(DEFAULT_REVIEWED_PATH, "--reviewed"),
        benchmark: Path | None = typer.Option(None, "--benchmark"),
    ):
        out = analyze_reviews_impl(review_queue=review_queue, reviewed=reviewed, benchmark_json=benchmark)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("compare-thresholds")
    def compare_thresholds_cmd(
        cases: Path = typer.Option(..., "--cases"),
        profiles: list[str] = typer.Option(["baseline", "strict", "loose"], "--profiles"),
        profile_config: Path = typer.Option(Path("config/event_threshold_profiles.yaml"), "--profile-config"),
    ):
        out = compare_thresholds_impl(cases_path=cases, profiles=profiles, profile_config=profile_config)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("analyze-errors")
    def analyze_errors_cmd(
        compare_json: Path = typer.Option(..., "--compare-json"),
        out_dir: Path | None = typer.Option(None, "--out-dir"),
    ):
        payload = _load_json(compare_json)
        out = error_analysis_impl(compare_payload=payload, out_dir=out_dir)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


    @app.command("rule-leaderboard")
    def rule_leaderboard_cmd(
        reviewed: Path = typer.Option(DEFAULT_REVIEWED_PATH, "--reviewed"),
        format: str = typer.Option("json", "--format"),
        out: Path | None = typer.Option(None, "--out"),
    ):
        out_payload = rule_leaderboard_impl(reviewed_path=reviewed, format=format, out_path=out)
        typer.echo(json.dumps(out_payload, ensure_ascii=False, indent=2))


    @app.command("tuning-report")
    def tuning_report_cmd(
        compare_json: Path = typer.Option(..., "--compare-json"),
        review_analysis_json: Path = typer.Option(..., "--review-analysis-json"),
        leaderboard_json: Path = typer.Option(..., "--leaderboard-json"),
        out_json: Path | None = typer.Option(None, "--out-json"),
        out_md: Path | None = typer.Option(None, "--out-md"),
    ):
        compare_payload = _load_json(compare_json)
        review_payload = _load_json(review_analysis_json)
        leaderboard_payload = (_load_json(leaderboard_json) or {}).get("rows", [])
        out_payload = tuning_report_impl(
            compare_payload=compare_payload,
            review_analysis_payload=review_payload,
            leaderboard_payload=leaderboard_payload,
            out_json=out_json,
            out_md=out_md,
        )
        typer.echo(json.dumps(out_payload, ensure_ascii=False, indent=2))

    @app.command("run-calibration-experiment")
    def run_calibration_experiment_cmd(
        profile: str = typer.Option(..., "--profile"),
        cases: Path = typer.Option(..., "--cases"),
        review_source: Path = typer.Option(DEFAULT_REVIEWED_PATH, "--review-source"),
    ):
        out = run_calibration_experiment_impl(profile=profile, cases=cases, review_source=review_source)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))

    @app.command("compare-profiles")
    def compare_profiles_cmd(
        compare_json: Path = typer.Option(..., "--compare-json"),
        baseline: str = typer.Option("baseline", "--baseline"),
        candidate: str = typer.Option(..., "--candidate"),
        out_md: Path | None = typer.Option(None, "--out-md"),
    ):
        payload = build_profile_compare_report(_load_json(compare_json), baseline=baseline, candidate=candidate)
        md = profile_compare_markdown(payload)
        if out_md:
            out_md.parent.mkdir(parents=True, exist_ok=True)
            out_md.write_text(md, encoding="utf-8")
        typer.echo(json.dumps({"report": payload, "markdown": md if not out_md else None, "out_md": str(out_md) if out_md else None}, ensure_ascii=False, indent=2))

    @app.command("propose-profile")
    def propose_profile_cmd(
        profile: str = typer.Option(..., "--profile"),
        source_file: str = typer.Option("config/event_threshold_profiles.yaml", "--source-file"),
        parent_profile: str | None = typer.Option(None, "--parent-profile"),
        change_summary: str = typer.Option("sprint11 proposal", "--change-summary"),
    ):
        out = propose_profile(profile_name=profile, source_file=source_file, parent_profile=parent_profile, change_summary=change_summary)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))

    @app.command("promote-profile")
    def promote_profile_cmd(
        profile: str = typer.Option(..., "--profile"),
        experiment_json: Path = typer.Option(..., "--experiment-json"),
        compare_json: Path = typer.Option(..., "--compare-json"),
    ):
        out = promote_profile(profile_name=profile, experiment_exists=experiment_json.exists(), compare_exists=compare_json.exists())
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))

    @app.command("rollback-profile")
    def rollback_profile_cmd(to: str = typer.Option(..., "--to")):
        out = rollback_profile(to_profile=to)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))

    @app.command("create-calibration-snapshot")
    def create_calibration_snapshot_cmd(
        experiment_json: Path = typer.Option(..., "--experiment-json"),
        recommendation_json: Path = typer.Option(..., "--recommendation-json"),
    ):
        out = create_calibration_snapshot(
            experiment_payload=_load_json(experiment_json),
            recommendation_summary=_load_json(recommendation_json),
        )
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))

    @app.command("run-batch")
    def run_batch_cmd(
        cases: Path = typer.Option(..., "--cases"),
        profiles: list[str] = typer.Option(["baseline", "strict"], "--profiles"),
    ):
        out = run_batch_impl(cases=cases, profiles=profiles)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))

    @app.command("export-batch-index")
    def export_batch_index_cmd(
        run: str = typer.Option(..., "--run"),
        format: str = typer.Option("json", "--format"),
    ):
        out = export_batch_index_impl(run_id=run, format=format)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))

    @app.command("profile-stability")
    def profile_stability_cmd(profile: str = typer.Option(..., "--profile")):
        out = profile_stability_impl(profile=profile)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))

    @app.command("export-layered-report")
    def export_layered_report_cmd(
        run: str = typer.Option(..., "--run"),
        level: str = typer.Option(..., "--level"),
    ):
        out = export_layered_report_impl(run_id=run, level=level)
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
    p_inspect.add_argument("--query-mode")
    p_inspect.add_argument("--literal-first", action="store_true")

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
    p_detect = sub.add_parser("detect-and-match")
    p_search = sub.add_parser("search-kb")
    p_search.add_argument("query")
    p_search.add_argument("--book-id")
    p_search.add_argument("--card-type", action="append")
    p_search.add_argument("--evidence-level")
    p_search.add_argument("--top-k", type=int, default=None)
    p_search.add_argument("--collection")
    p_search.add_argument("--query-mode")
    p_search.add_argument("--literal-first", action="store_true")
    p_search.add_argument("--literal-pool-factor", type=int, default=None)
    p_search.add_argument("--base-url")
    p_search.add_argument("--api-key")
    p_candidate = sub.add_parser("generate-candidate-card")
    p_candidate.add_argument("--query", required=True)
    p_candidate.add_argument("--book-id", required=True)
    p_candidate.add_argument("--out-dir", required=True)
    p_candidate.add_argument("--limit", type=int, default=None)
    p_candidate.add_argument("--base-url")
    p_candidate.add_argument("--api-key")
    p_sync = sub.add_parser("sync-upstream-status")
    p_sync.add_argument("--book-id", required=True)
    p_sync.add_argument("--candidate-root", default="data/generated_candidates")
    p_sync.add_argument("--base-url")
    p_sync.add_argument("--api-key")
    p_detect.add_argument("--datetime", required=True)
    p_detect.add_argument("--lon", type=float, required=True)
    p_detect.add_argument("--lat", type=float, required=True)
    p_detect.add_argument("--body", default="mars")
    p_detect.add_argument("--target", default="xin_xiu")
    p_detect.add_argument("--rules-path", default="data/processed/corpus/sample_rules.json")
    p_detect.add_argument("--kb-root")
    p_detect.add_argument("--ephemeris-path")
    p_detect.add_argument("--force-fallback", action="store_true")
    p_detect.add_argument("--cluster-window-days", type=int, default=3)
    p_detect.add_argument("--peak-selection-rule", default="min_angular_distance")
    p_replay = sub.add_parser("replay-event")
    p_replay.add_argument("--case", required=True)
    p_replay.add_argument("--rules-path", default="data/processed/corpus/sample_rules.json")
    p_replay.add_argument("--kb-root")
    p_replay.add_argument("--ephemeris-path")
    p_scan = sub.add_parser("scan-window")
    p_scan.add_argument("--start", required=True)
    p_scan.add_argument("--end", required=True)
    p_scan.add_argument("--lon", type=float, required=True)
    p_scan.add_argument("--lat", type=float, required=True)
    p_scan.add_argument("--bodies", action="append", default=[])
    p_scan.add_argument("--targets", action="append", default=[])
    p_scan.add_argument("--event-types", action="append", default=[])
    p_scan.add_argument("--rules-path", default="data/processed/corpus/sample_rules.json")
    p_scan.add_argument("--kb-root")
    p_scan.add_argument("--ephemeris-path")
    p_scan.add_argument("--force-fallback", action="store_true")
    p_scan.add_argument("--cluster-window-days", type=int, default=3)
    p_scan.add_argument("--peak-selection-rule", default="min_angular_distance")
    p_scan.add_argument("--step-hours", type=int, default=24)
    p_benchmark = sub.add_parser("benchmark-window")
    p_benchmark.add_argument("--case", required=True)
    p_benchmark.add_argument("--rules-path", default="data/processed/corpus/sample_rules.json")
    p_benchmark.add_argument("--ephemeris-path")
    p_benchmark.add_argument("--force-fallback", action="store_true")
    p_benchmark.add_argument("--export-md")
    p_build_review = sub.add_parser("build-review-queue")
    p_build_review.add_argument("--from-benchmark", required=True)
    p_build_review.add_argument("--queue-path", default=str(DEFAULT_QUEUE_PATH))
    p_review_item = sub.add_parser("review-item")
    p_review_item.add_argument("--id", required=True)
    p_review_item.add_argument("--status", required=True)
    p_review_item.add_argument("--notes", default="")
    p_review_item.add_argument("--queue-path", default=str(DEFAULT_QUEUE_PATH))
    p_review_item.add_argument("--reviewed-path", default=str(DEFAULT_REVIEWED_PATH))
    p_export_review = sub.add_parser("export-review")
    p_export_review.add_argument("--format", default="md")
    p_export_review.add_argument("--benchmark")
    p_export_review.add_argument("--queue-path", default=str(DEFAULT_QUEUE_PATH))
    p_export_review.add_argument("--out")
    p_analyze_reviews = sub.add_parser("analyze-reviews")
    p_analyze_reviews.add_argument("--review-queue", default=str(DEFAULT_QUEUE_PATH))
    p_analyze_reviews.add_argument("--reviewed", default=str(DEFAULT_REVIEWED_PATH))
    p_analyze_reviews.add_argument("--benchmark")
    p_compare = sub.add_parser("compare-thresholds")
    p_compare.add_argument("--cases", required=True)
    p_compare.add_argument("--profiles", action="append", default=[])
    p_compare.add_argument("--profile-config", default="config/event_threshold_profiles.yaml")
    p_err = sub.add_parser("analyze-errors")
    p_err.add_argument("--compare-json", required=True)
    p_err.add_argument("--out-dir")
    p_lb = sub.add_parser("rule-leaderboard")
    p_lb.add_argument("--reviewed", default=str(DEFAULT_REVIEWED_PATH))
    p_lb.add_argument("--format", default="json")
    p_lb.add_argument("--out")
    p_tune = sub.add_parser("tuning-report")
    p_tune.add_argument("--compare-json", required=True)
    p_tune.add_argument("--review-analysis-json", required=True)
    p_tune.add_argument("--leaderboard-json", required=True)
    p_tune.add_argument("--out-json")
    p_tune.add_argument("--out-md")

    p_run_exp = sub.add_parser("run-calibration-experiment")
    p_run_exp.add_argument("--profile", required=True)
    p_run_exp.add_argument("--cases", required=True)
    p_run_exp.add_argument("--review-source", default=str(DEFAULT_REVIEWED_PATH))
    p_cmp_prof = sub.add_parser("compare-profiles")
    p_cmp_prof.add_argument("--compare-json", required=True)
    p_cmp_prof.add_argument("--baseline", default="baseline")
    p_cmp_prof.add_argument("--candidate", required=True)
    p_cmp_prof.add_argument("--out-md")
    p_prop = sub.add_parser("propose-profile")
    p_prop.add_argument("--profile", required=True)
    p_prop.add_argument("--source-file", default="config/event_threshold_profiles.yaml")
    p_prop.add_argument("--parent-profile")
    p_prop.add_argument("--change-summary", default="sprint11 proposal")
    p_prom = sub.add_parser("promote-profile")
    p_prom.add_argument("--profile", required=True)
    p_prom.add_argument("--experiment-json", required=True)
    p_prom.add_argument("--compare-json", required=True)
    p_rb = sub.add_parser("rollback-profile")
    p_rb.add_argument("--to", required=True)
    p_snap = sub.add_parser("create-calibration-snapshot")
    p_snap.add_argument("--experiment-json", required=True)
    p_snap.add_argument("--recommendation-json", required=True)

    p_run_batch = sub.add_parser("run-batch")
    p_run_batch.add_argument("--cases", required=True)
    p_run_batch.add_argument("--profiles", action="append", default=[])
    p_exp_idx = sub.add_parser("export-batch-index")
    p_exp_idx.add_argument("--run", required=True)
    p_exp_idx.add_argument("--format", default="json")
    p_stab = sub.add_parser("profile-stability")
    p_stab.add_argument("--profile", required=True)
    p_layer = sub.add_parser("export-layered-report")
    p_layer.add_argument("--run", required=True)
    p_layer.add_argument("--level", required=True)

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
            args.query_mode,
            (True if args.literal_first else None),
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
    elif args.cmd == "search-kb":
        retriever = KBSearchRetriever(base_url=args.base_url, api_key=args.api_key)
        filters: dict[str, Any] = {}
        if args.book_id:
            filters["kb_book_id"] = args.book_id
        if args.card_type:
            filters["card_type"] = args.card_type
        if args.evidence_level:
            filters["evidence_level"] = args.evidence_level
        try:
            out = retriever.search(
                args.query,
                top_k=args.top_k,
                limit=args.top_k,
                collection=args.collection,
                filters=filters or None,
                query_mode=args.query_mode,
                literal_first=(True if args.literal_first else None),
                literal_pool_factor=args.literal_pool_factor,
            )
        except Exception as exc:
            out = {"mode": "search", "query": args.query, "error": str(exc), "hint": "check KB_SEARCH_API_KEY and kb-search service"}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "generate-candidate-card":
        out = generate_candidate_card_impl(
            args.query,
            args.book_id,
            Path(args.out_dir),
            limit=args.limit,
            base_url=args.base_url,
            api_key=args.api_key,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "sync-upstream-status":
        out = sync_upstream_status_impl(
            args.book_id,
            Path(args.candidate_root),
            base_url=args.base_url,
            api_key=args.api_key,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "detect-and-match":
        out = run_detect_and_match_pipeline(
            datetime_utc=args.datetime,
            lon=args.lon,
            lat=args.lat,
            body=args.body,
            target=args.target,
            rules_path=Path(args.rules_path),
            kb_root=Path(args.kb_root) if args.kb_root else None,
            ephemeris_path=args.ephemeris_path,
            force_fallback=args.force_fallback,
            cluster_window_days=args.cluster_window_days,
            peak_selection_rule=args.peak_selection_rule,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "replay-event":
        out = replay_event_impl(
            case_path=Path(args.case),
            rules_path=Path(args.rules_path),
            kb_root=Path(args.kb_root) if args.kb_root else None,
            ephemeris_path=args.ephemeris_path,
        )
        print(
            json.dumps(out, ensure_ascii=False, indent=2)
        )
    elif args.cmd == "scan-window":
        out = scan_window_impl(
            start_datetime_utc=args.start,
            end_datetime_utc=args.end,
            lon=args.lon,
            lat=args.lat,
            bodies=args.bodies or ["mars", "moon", "jupiter", "saturn"],
            targets=args.targets or ["xin_xiu", "jiao_xiu", "fang_xiu"],
            event_types=args.event_types or ["guarding", "invading", "conjunction", "gathering"],
            rules_path=Path(args.rules_path),
            kb_root=Path(args.kb_root) if args.kb_root else None,
            ephemeris_path=args.ephemeris_path,
            force_fallback=args.force_fallback,
            cluster_window_days=args.cluster_window_days,
            peak_selection_rule=args.peak_selection_rule,
            step_hours=args.step_hours,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "benchmark-window":
        out = benchmark_window_impl(
            case_path=Path(args.case),
            rules_path=Path(args.rules_path),
            ephemeris_path=args.ephemeris_path,
            force_fallback=args.force_fallback,
        )
        if args.export_md:
            export_path = Path(args.export_md)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(export_benchmark_markdown(out), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "build-review-queue":
        out = build_review_queue_impl(benchmark_path=Path(args.from_benchmark), queue_path=Path(args.queue_path))
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "review-item":
        out = review_item_impl(
            review_item_id=args.id,
            status=args.status,
            notes=args.notes,
            queue_path=Path(args.queue_path),
            reviewed_path=Path(args.reviewed_path),
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "export-review":
        out = export_review_impl(
            benchmark_path=Path(args.benchmark) if args.benchmark else None,
            queue_path=Path(args.queue_path),
            out_path=Path(args.out) if args.out else None,
            format=args.format,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "analyze-reviews":
        out = analyze_reviews_impl(
            review_queue=Path(args.review_queue),
            reviewed=Path(args.reviewed),
            benchmark_json=Path(args.benchmark) if args.benchmark else None,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "compare-thresholds":
        out = compare_thresholds_impl(
            cases_path=Path(args.cases),
            profiles=args.profiles or ["baseline", "strict", "loose"],
            profile_config=Path(args.profile_config),
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "analyze-errors":
        out = error_analysis_impl(
            compare_payload=_load_json(Path(args.compare_json)),
            out_dir=Path(args.out_dir) if args.out_dir else None,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "rule-leaderboard":
        out = rule_leaderboard_impl(
            reviewed_path=Path(args.reviewed),
            format=args.format,
            out_path=Path(args.out) if args.out else None,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))

    elif args.cmd == "run-calibration-experiment":
        out = run_calibration_experiment_impl(profile=args.profile, cases=Path(args.cases), review_source=Path(args.review_source))
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "compare-profiles":
        rep = build_profile_compare_report(_load_json(Path(args.compare_json)), baseline=args.baseline, candidate=args.candidate)
        md = profile_compare_markdown(rep)
        if args.out_md:
            Path(args.out_md).write_text(md, encoding="utf-8")
        print(json.dumps({"report": rep, "markdown": md if not args.out_md else None, "out_md": args.out_md}, ensure_ascii=False, indent=2))
    elif args.cmd == "propose-profile":
        out = propose_profile(profile_name=args.profile, source_file=args.source_file, parent_profile=args.parent_profile, change_summary=args.change_summary)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "promote-profile":
        out = promote_profile(profile_name=args.profile, experiment_exists=Path(args.experiment_json).exists(), compare_exists=Path(args.compare_json).exists())
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "rollback-profile":
        out = rollback_profile(to_profile=args.to)
        print(json.dumps(out, ensure_ascii=False, indent=2))

    elif args.cmd == "run-batch":
        out = run_batch_impl(cases=Path(args.cases), profiles=args.profiles or ["baseline", "strict"])
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "export-batch-index":
        out = export_batch_index_impl(run_id=args.run, format=args.format)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "profile-stability":
        out = profile_stability_impl(profile=args.profile)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "export-layered-report":
        out = export_layered_report_impl(run_id=args.run, level=args.level)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "create-calibration-snapshot":
        out = create_calibration_snapshot(experiment_payload=_load_json(Path(args.experiment_json)), recommendation_summary=_load_json(Path(args.recommendation_json)))
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.cmd == "tuning-report":
        leaderboard_payload = (_load_json(Path(args.leaderboard_json)) or {}).get("rows", [])
        out = tuning_report_impl(
            compare_payload=_load_json(Path(args.compare_json)),
            review_analysis_payload=_load_json(Path(args.review_analysis_json)),
            leaderboard_payload=leaderboard_payload,
            out_json=Path(args.out_json) if args.out_json else None,
            out_md=Path(args.out_md) if args.out_md else None,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if typer:
        app()
    else:
        _main_fallback()

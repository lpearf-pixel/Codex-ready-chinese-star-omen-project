import json

from src.connectors.manifest_reader import ManifestReader


def test_manifest_inspect_and_load(tmp_path):
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    data = {"book_id": "kaiyuan_zhanjing"}
    (mdir / "kaiyuan_zhanjing.json").write_text(json.dumps(data), encoding="utf-8")

    reader = ManifestReader(tmp_path)
    assert "kaiyuan_zhanjing.json" in reader.inspect()["manifests"]
    assert reader.load_manifest("manifest:kaiyuan_zhanjing")["book_id"] == "kaiyuan_zhanjing"


def test_manifest_missing_is_compatible(tmp_path):
    reader = ManifestReader(tmp_path)
    out = reader.load_manifest("manifest:not_found")
    assert out["manifest_found"] is False

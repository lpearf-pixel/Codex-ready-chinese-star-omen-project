from src.astronomy.asterism_matcher_impl import MinimalAsterismMatcher


def test_asterism_matcher_outputs_contract_fields():
    matcher = MinimalAsterismMatcher()
    out = matcher.match(points=[{"body": "mars", "ecliptic_lon": 241.1}], targets=["xin_xiu"])
    assert out
    row = out[0]
    for field in ["matched_asterism_id", "matched_asterism_name", "angular_distance_deg", "match_basis", "confidence"]:
        assert field in row

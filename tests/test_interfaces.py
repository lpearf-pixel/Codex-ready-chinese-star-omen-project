from src.interfaces import AsterismMatcher, CelestialEventDetector, EphemerisProvider, OmenRuleExecutor


def test_interfaces_are_importable():
    assert EphemerisProvider is not None
    assert AsterismMatcher is not None
    assert CelestialEventDetector is not None
    assert OmenRuleExecutor is not None

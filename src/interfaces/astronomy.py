from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass
class EphemerisPoint:
    body: str
    datetime_utc: datetime
    ra_deg: float
    dec_deg: float
    ecl_lon_deg: float
    ecl_lat_deg: float
    magnitude: float | None = None


@dataclass
class MatchResult:
    asterism_id: str
    confidence: float
    matched_stars: list[str]
    notes: str | None = None


class EphemerisProvider(Protocol):
    """Provide deterministic ephemeris points.

    Input: body names + UTC timestamps.
    Output: normalized ephemeris coordinates in degrees.
    Responsibility: astronomical state lookup only.
    Not responsible for: omen interpretation or rule execution.
    """

    def get_points(self, *, bodies: list[str], at: list[datetime]) -> list[EphemerisPoint]:
        ...


class AsterismMatcher(Protocol):
    """Map ephemeris points into traditional asterism space.

    Input: ephemeris points + asterism catalog metadata.
    Output: match results with confidence.
    Responsibility: matching logic only.
    Not responsible for: event detection windows or omen scoring.
    """

    def match(self, *, points: list[EphemerisPoint], asterisms: list[dict[str, Any]]) -> list[MatchResult]:
        ...


class CelestialEventDetector(Protocol):
    """Detect event candidates from matched trajectories.

    Input: time-ordered match results and optional thresholds.
    Output: event dicts compatible with CelestialEvent schema fields.
    Responsibility: event detection and normalization.
    Not responsible for: historical rule judgment/backtesting.
    """

    def detect(self, *, matches: list[MatchResult], config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ...


class OmenRuleExecutor(Protocol):
    """Execute omen rules against detected events.

    Input: events + OmenRule records.
    Output: rule match payload compatible with BacktestRecord fragments.
    Responsibility: deterministic rule evaluation.
    Not responsible for: ephemeris calculation, narrative generation, or publishing.
    """

    def execute(self, *, events: list[dict[str, Any]], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ...

"""Canonical input binding, not a training quality certificate."""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from custom_components.helios_forecast.openmeteo import WeatherSeries
from custom_components.helios_forecast.provenance import build_provenance, digest, implementation
from custom_components.helios_forecast.solar.residual import ProductionBucket


def _inputs():
    now = datetime.now(timezone.utc) - timedelta(minutes=1)
    weather = WeatherSeries([now], [0], [100], [70], [30], [20], [5], [0], received_at=now, retrieval="network")
    return dict(
        weather=weather,
        config={"latitude": 50, "cap": float("inf")},
        buckets=[ProductionBucket(now.timestamp() * 1000, (now + timedelta(hours=1)).timestamp() * 1000, 1.0)],
        requested_start=now - timedelta(days=60),
        requested_end=now,
        history_read=True,
        stale=False,
    )


def test_hashes_describe_inputs_and_unknown_stays_unknown():
    args = _inputs()
    first = build_provenance(**args)
    assert first["schema_version"] == "helios.forecast.v1"
    assert first["weather"]["received_at"] == args["weather"].received_at.isoformat()
    assert first["weather"]["issue_time"] is None
    assert first["learning"]["trained_until"] is None
    assert first["learning"]["constraint_quality"] == "unknown"
    assert first["learning"]["strict"] is False
    assert first["point_estimate"] == "corrected_model_point"
    assert datetime.fromisoformat(first["computed_at"]) >= args["requested_end"]
    json.dumps(first, allow_nan=False)
    assert first["model"]["version"]
    assert first["model"]["implementation_sha256"] == digest(implementation()["source_files"])
    cached = build_provenance(**{**args, "weather": replace(args["weather"], retrieval="cache")})
    assert cached["weather"]["content_sha256"] == first["weather"]["content_sha256"]
    assert cached["weather"]["received_at"] == first["weather"]["received_at"]
    assert cached["weather"]["retrieval"] == "cache"
    stale = build_provenance(**{**args, "stale": True})
    assert stale["weather"]["retrieval"] == "stale"
    changed = build_provenance(**{**args, "weather": replace(args["weather"], shortwave=[200])})
    assert changed["weather"]["content_sha256"] != first["weather"]["content_sha256"]
    assert (
        build_provenance(**{**args, "config": {"latitude": 51}})["configuration_sha256"]
        != first["configuration_sha256"]
    )
    assert build_provenance(**{**args, "buckets": []})["learning"]["input_sha256"] != first["learning"]["input_sha256"]


def test_canonical_key_order_and_missing_receipt():
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    args = _inputs()
    args["weather"] = replace(args["weather"], received_at=None, retrieval="unknown")
    result = build_provenance(**args)
    assert result["weather"]["received_at"] is None
    assert result["weather"]["http_receipts"] == []

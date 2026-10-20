"""Versioned reproducibility metadata, without claims of calibrated training quality."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "helios.forecast.v1"


def canonical(value: Any) -> Any:
    """JSON-safe canonical inputs; explicit non-finite markers preserve config infinity."""
    if is_dataclass(value) and not isinstance(value, type):
        return canonical(asdict(value))
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite_float": str(value)}
    return value


def digest(value: Any) -> str:
    """SHA256 of UTF-8 canonical JSON (sorted keys, compact separators)."""
    raw = json.dumps(canonical(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def http_receipt(payload: dict) -> dict:
    """The successful parsed HTTP JSON response; no guessed provider issue time."""
    return {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": digest(payload),
        "issue_time": None,
    }


@lru_cache(maxsize=1)
def implementation() -> dict:
    """Fingerprint the installed package sources, not a guessed model/feature version."""
    root = Path(__file__).parent
    files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*.py"))}
    manifest = json.loads((root / "manifest.json").read_text())
    return {"version": manifest["version"], "implementation_sha256": digest(files), "source_files": files}


def build_provenance(*, weather, config, buckets, requested_start, requested_end, history_read, stale, quality=None):
    """Bind the inputs actually used. Called in the executor after computation."""
    values = asdict(weather)
    values.pop("received_at", None)
    receipts = values.pop("receipts", [])
    values.pop("retrieval", None)
    return {
        "schema_version": SCHEMA_VERSION,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "point_estimate": "corrected_model_point",
        "weather": {
            "received_at": weather.received_at.isoformat() if weather.received_at else None,
            "content_sha256": digest(values),
            "http_receipts": receipts,
            "issue_time": None,
            "retrieval": "stale" if stale else weather.retrieval,
        },
        "configuration_sha256": digest(config),
        "model": implementation(),
        "learning": {
            "requested_start": requested_start.isoformat(),
            "requested_end": requested_end.isoformat(),
            "history_read": history_read,
            "input_sha256": digest(buckets),
            "input_count": len(buckets),
            "input_start_ms": min((b.start_ms for b in buckets), default=None),
            "input_end_ms": max((b.end_ms for b in buckets), default=None),
            "trained_until": None,
            "constraint_quality": (quality or {}).get("status", "unknown"),
            "strict": (quality or {}).get("strict", False),
            "quality_counts": (quality or {}).get("counts"),
        },
    }

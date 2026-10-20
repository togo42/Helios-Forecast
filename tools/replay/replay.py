"""Replay the learning offline, day after day, against what the roof really produced.

The real residual map and analog library are rebuilt from production available at 06:00 local,
then subsequent daylight hours are scored against the meter. Weather is the retrospective hourly
archive and may contain later corrections: this isolates learning conditional on archived weather,
not the skill of original issued forecasts. Optional variants are uncalibrated research comparisons.

Usage: python tools/replay/replay.py --config CONFIG --data-dir DATA --days 30
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from custom_components.helios_forecast import analog  # noqa: E402
from custom_components.helios_forecast.analog import AnalogSample, build_library, enrich_points  # noqa: E402
from custom_components.helios_forecast.forecast import (  # noqa: E402
    build_forecast_series,
    hardware_power_limit_w,
    limit_forecast_power,
)
from custom_components.helios_forecast.openmeteo import WeatherSeries  # noqa: E402
from custom_components.helios_forecast.solar.geometry import sun_position  # noqa: E402
from custom_components.helios_forecast.solar.power import (  # noqa: E402
    PanelOrientation,
    PvLayout,
)
from custom_components.helios_forecast.solar import residual as RS  # noqa: E402
from custom_components.helios_forecast.solar.residual import (  # noqa: E402
    LEARN_DAYS,
    ProductionBucket,
    SkyResidualInput,
    SkyResidualMap,
    build_sky_residual_map,
    implausible_hour,
)


@dataclass(frozen=True)
class ReplayConfig:
    """Explicit local installation inputs; never inferred from another installation."""

    lat: float
    lon: float
    timezone: ZoneInfo
    layout: PvLayout
    inverter_max_w: float
    entry_id: str = ""
    production_statistic: str = ""

    @classmethod
    def load(cls, path: Path) -> ReplayConfig:
        raw = json.loads(path.read_text())
        if not isinstance(raw["entry_id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]+", raw["entry_id"]):
            raise ValueError("entry_id must be a config entry identifier")
        if not isinstance(raw["production_statistic"], str) or not raw["production_statistic"]:
            raise ValueError("production_statistic is required")
        lat = _number(raw["latitude"], "latitude", -90, 90)
        lon = _number(raw["longitude"], "longitude", -180, 180)
        arrays = raw["arrays"]
        if not arrays:
            raise ValueError("arrays must contain at least one panel line")
        sizes = [_number(a["kwp"], "kwp", 0, math.inf, positive=True) for a in arrays]
        coords = []
        for a in arrays:
            if ("latitude" in a) != ("longitude" in a):
                raise ValueError("per-line latitude and longitude must be supplied together")
            coords.append(
                (_number(a["latitude"], "latitude", -90, 90), _number(a["longitude"], "longitude", -180, 180))
                if "latitude" in a
                else None
            )
            if a.get("tracker") not in (None, "dual-axis", "single-axis-h", "single-axis-v"):
                raise ValueError("unsupported tracker")
        total = _number(sum(sizes), "total_kwp", 0, math.inf, positive=True)
        layout = PvLayout(
            orientations=[
                PanelOrientation(
                    _number(a["tilt_deg"], "tilt_deg", 0, 90),
                    _number(a["azimuth_deg"], "azimuth_deg", 0, 360),
                    a.get("tracker"),
                )
                for a in arrays
            ],
            shares=[size / total for size in sizes],
            coords=coords,
            total_kwp=total,
            caps=[_cap(a.get("inverter_max_w")) for a in arrays],
        )
        return cls(
            lat,
            lon,
            ZoneInfo(raw["timezone"]),
            layout,
            _cap(raw.get("inverter_max_w")),
            raw["entry_id"].lower(),
            raw["production_statistic"],
        )


def _number(value, name, low, high, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if not low <= value <= high or (positive and value <= 0):
        raise ValueError(f"{name} outside supported range")
    return float(value)


def _cap(value):
    return math.inf if value is None else _number(value, "inverter_max_w", 0, math.inf, positive=True)


def _finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


WEATHER_FIELDS = ("cloud_cover", "ghi", "direct", "diffuse", "temperature", "wind_speed", "snow_depth")


def load_weather(data_dir: Path) -> WeatherSeries:
    raw = json.loads((data_dir / "weather.json").read_text())
    by_t = {}
    for field in WEATHER_FIELDS:
        for start_ms, mean in raw.get(field, []):
            if not _finite(start_ms) or start_ms % 3_600_000:
                raise ValueError("weather timestamps must be UTC hour starts in epoch milliseconds")
            value = float(mean) if _finite(mean) else None
            if field != "temperature" and value is not None and value < 0:
                value = None
            if field == "cloud_cover" and value is not None and value > 100:
                value = None
            hour = by_t.setdefault(int(start_ms), {})
            if field in hour and hour[field] != value:
                raise ValueError(f"conflicting weather values for {field} at {start_ms}")
            hour[field] = value
    times = sorted(by_t)
    values = [[by_t[t].get(field) for t in times] for field in WEATHER_FIELDS]
    return WeatherSeries(
        times=[datetime.fromtimestamp(t / 1000, tz=timezone.utc) for t in times],
        cloud=values[0],
        shortwave=values[1],
        direct=values[2],
        diffuse=values[3],
        temp=values[4],
        wind=values[5],
        snow=values[6],
    )


def load_production(data_dir: Path) -> List[ProductionBucket]:
    rows = json.loads((data_dir / "production.json").read_text())
    out = {}
    for start_ms, end_ms, change in rows:
        if not _finite(start_ms) or not _finite(end_ms):
            continue
        if end_ms - start_ms != 3_600_000 or start_ms % 3_600_000:
            raise ValueError("production must contain UTC-aligned one-hour kWh changes")
        if not _finite(change) or change < 0:
            continue
        bucket = ProductionBucket(float(start_ms), float(end_ms), float(change))
        if start_ms in out and out[start_ms] != bucket:
            raise ValueError(f"conflicting production values at {start_ms}")
        out[start_ms] = bucket
    return [out[t] for t in sorted(out)]


def measured_map(buckets: List[ProductionBucket]) -> Dict[int, float]:
    """Validated hourly kWh; valid measured zero remains a scoreable observation."""
    out = {}
    for b in buckets:
        if not _finite(b.kwh) or b.kwh < 0 or b.end_ms - b.start_ms != 3_600_000:
            continue
        if b.start_ms % 3_600_000:
            continue
        if b.start_ms in out and out[b.start_ms] != b.kwh:
            raise ValueError("conflicting production observations")
        out[int(b.start_ms)] = b.kwh
    return out


def usable_weather_hours(weather: WeatherSeries) -> set[int]:
    """Require actual adjacent-hour cloud and irradiance evidence, never fill a gap."""
    usable = set()
    for i, t in enumerate(weather.times):
        if not _finite(weather.cloud[i]) or not 0 <= weather.cloud[i] <= 100:
            continue
        ghi = weather.shortwave[i]
        direct, diffuse = weather.direct[i], weather.diffuse[i]
        if (_finite(ghi) and ghi >= 0) or (all(_finite(v) and v >= 0 for v in (direct, diffuse))):
            usable.add(int(t.timestamp() * 1000))
    return {t for t in usable if t + 3_600_000 in usable}


# ---- variants of the analog step ------------------------------------------------------------------


def predict_variant(library, alt, az, cloud, temp, *, narrow_alt=False, az_weight=None, az_norm=180.0):
    """analog.predict with switches: altitude distance relative to the altitude itself (a low sun only
    matches a low sun), and a heavier, tighter azimuth term so a September evening at 271 degrees is not
    told by July evenings at 290 that lay behind a different piece of horizon."""
    if not library or alt <= 0:
        return None
    w_az = analog._W_AZ if az_weight is None else az_weight
    scored = []
    for s in library:
        dalt = (s.alt - alt) / (max(alt, 10.0) if narrow_alt else 90.0)
        daz = analog._az_diff(s.az, az) / az_norm
        dcl = (s.cloud - cloud) / 100.0
        d2 = analog._W_ALT * dalt * dalt + w_az * daz * daz + analog._W_CLOUD * dcl * dcl
        if temp is not None and s.temp is not None:
            dt = (s.temp - temp) / analog._TEMP_SCALE
            d2 += analog._W_TEMP * dt * dt
        else:
            d2 += analog._TEMP_MISSING_PENALTY
        scored.append((d2, s.watt))
    scored.sort(key=lambda x: x[0])
    top = scored[: analog._K]
    weighted = [(v, math.exp(-d2 / (2.0 * analog._BANDWIDTH2))) for d2, v in top]
    p10, p50, p90 = analog._weighted_percentiles(weighted, (0.10, 0.50, 0.90))
    n_close = sum(1 for d2, _ in top if d2 <= analog._CLOSE_D2)
    confidence = min(1.0, n_close / analog._CONFIDENCE_FULL)
    ceiling = p90 * analog._CEILING_MARGIN if n_close >= analog._CEILING_MIN_ANALOGS else None
    return analog.AnalogBand(p10=p10, p50=p50, p90=p90, confidence=confidence, ceiling=ceiling)


def enrich_variant(
    points,
    library,
    weather,
    w_epochs,
    now,
    *,
    ratio_lib=False,
    narrow_alt=False,
    max_conf=1.0,
    az_weight=None,
    az_norm=180.0,
    config,
):
    if not library:
        return points
    out = []
    for p in points:
        if p.t < now:
            out.append(p)
            continue
        sun = sun_position(p.t, config.lat, config.lon)
        if sun.altitude <= 0:
            out.append(replace(p, pv_p10=0.0, pv_p90=0.0))
            continue
        ms = p.t.timestamp() * 1000.0
        cloud = analog._sample_series(weather.times, weather.cloud, ms, w_epochs)
        temp = analog._sample_series(weather.times, weather.temp, ms, w_epochs)
        band = predict_variant(
            library,
            sun.altitude,
            sun.azimuth,
            cloud if cloud is not None else 50.0,
            temp,
            narrow_alt=narrow_alt,
            az_weight=az_weight,
            az_norm=az_norm,
        )
        if band is None:
            out.append(p)
            continue
        c = min(max_conf, band.confidence)
        if ratio_lib:
            # The library holds actual/physics ratios: the analog's word is a ratio applied to today's physics.
            p50, p10, p90 = band.p50 * p.pv_raw_w, band.p10 * p.pv_raw_w, band.p90 * p.pv_raw_w
            ceiling = band.ceiling * p.pv_raw_w if band.ceiling is not None else None
        else:
            p50, p10, p90, ceiling = band.p50, band.p10, band.p90, band.ceiling
        blended = c * p50 + (1.0 - c) * p.pv_w
        if ceiling is not None:
            blended = min(blended, ceiling)
        out.append(
            replace(p, pv_w=blended, pv_p10=p10, pv_p90=p90)
            if band.confidence >= analog.BAND_MIN_CONFIDENCE
            else replace(p, pv_w=blended)
        )
    return out


def ratio_library(library) -> List[AnalogSample]:
    """Exploratory ratio values from the same validated model samples, without re-pairing rows."""
    return [replace(s, watt=s.ratio) for s in analog.ratio_samples(library)]


# ---- a variant of the residual map's smoothing ---------------------------------------------------


def vertical_map(inp: SkyResidualInput) -> Optional[SkyResidualMap]:
    """The residual map with its thin cells filled from the sky ABOVE and BELOW them at the same azimuth
    first, and from the side cells only when that column is empty.

    Near-field shading is a property of azimuth: an obstacle at 288 degrees darkens every cell under its
    own height at 288 and nothing at 271. The integration's smoothing pulls a thin cell toward all eight
    neighbours alike, so a cell the sun only reaches this month borrows the shading of the azimuths it
    reached last month. The column above it is a better witness."""
    keep = RS.SMOOTH_NEIGHBOR_W
    # Not zero: the integration's own smoothing divides by the pull, so an all-but-absent pull leaves the
    # raw cells untouched without tripping it.
    RS.SMOOTH_NEIGHBOR_W = 1e-9
    try:
        raw = build_sky_residual_map(inp)
    finally:
        RS.SMOOTH_NEIGHBOR_W = keep
    if raw is None:
        return None
    m, conf, n_az, n_alt = list(raw.m), list(raw.conf), raw.n_az, raw.n_alt
    m_s, c_s = list(m), list(conf)
    for aj in range(n_alt):
        for ai in range(n_az):
            idx = aj * n_az + ai
            if conf[idx] >= RS.SMOOTH_CONF_KEEP:
                continue
            num = den = best = 0.0
            for d_alt in (-1, 1, -2, 2):
                nj = aj + d_alt
                if 0 <= nj < n_alt:
                    c = conf[nj * n_az + ai] / abs(d_alt)
                    num += c * m[nj * n_az + ai]
                    den += c
                    best = max(best, conf[nj * n_az + ai])
            if den <= 0:
                for d_az in (-1, 1):
                    ni = (ai + d_az) % n_az
                    c = conf[aj * n_az + ni]
                    num += c * m[aj * n_az + ni]
                    den += c
                    best = max(best, c)
            if den <= 0 or best <= 0:
                continue
            pull = keep * best
            m_s[idx] = (conf[idx] * m[idx] + pull * (num / den)) / (conf[idx] + pull)
            c_s[idx] = min(1.0, conf[idx] + pull)
    return replace(raw, m=m_s, conf=c_s)


# ---- the replay ------------------------------------------------------------------------------------

BANDS = ["AM 0-15", "AM 15-30", "AM 30+", "PM 30+", "PM 15-30", "PM 0-15"]


def band_of(sun) -> str:
    half = "AM" if sun.azimuth < 180 else "PM"
    alt = sun.altitude
    return "%s %s" % (half, "0-15" if alt < 15 else ("15-30" if alt < 30 else "30+"))


def score_points(points, measured, config, now, usable_hours):
    """Match four quarter-hours to one measured hourly energy change.

    Instantaneous P10/P90 cannot be scored against hourly energy; no band coverage is inferred.
    """
    by_hour = {}
    for point in points:
        hour = int(point.t.timestamp() * 1000) // 3_600_000 * 3_600_000
        by_hour.setdefault(hour, []).append(point)
    scores = {band: {"n": 0, "abs_w": 0.0, "pred_kwh": 0.0, "truth_kwh": 0.0} for band in BANDS + ["total"]}
    for hour, group in by_hour.items():
        if hour not in measured or hour not in usable_hours or hour < now.timestamp() * 1000:
            continue
        expected = {hour + i * 900_000 for i in range(4)}
        if len(group) != 4 or {int(p.t.timestamp() * 1000) for p in group} != expected:
            continue
        if any(not _finite(p.pv_w) for p in group):
            continue
        mid = datetime.fromtimestamp(hour / 1000 + 1800, tz=timezone.utc)
        sun = sun_position(mid, config.lat, config.lon)
        if sun.altitude <= 0:
            continue
        truth = measured[hour]
        if not _finite(truth) or truth < 0 or implausible_hour(truth, hour, hour + 3_600_000, config.layout.total_kwp):
            continue
        pred = sum(p.pv_w for p in group) / 4 / 1000
        for key in (band_of(sun), "total"):
            score = scores[key]
            score["n"] += 1
            score["abs_w"] += abs(pred - truth) * 1000
            score["pred_kwh"] += pred
            score["truth_kwh"] += truth
    return scores


def run_replay(weather, buckets, config, first_day, end_day, *, variants=False):
    """Rebuild learners at 06:00 local for each date in [first_day, end_day).

    Only production strictly before the evaluation origin is used for training. Archived weather
    is retrospective: this tests the learner conditional on archived weather, not forecast skill.
    """
    if first_day >= end_day:
        raise ValueError("first day must precede exclusive end day")
    for boundary in (first_day, end_day):
        if boundary.tzinfo is None or boundary.astimezone(config.timezone).time() != datetime.min.time():
            raise ValueError("replay boundaries must be local midnights")
    measured = measured_map(buckets)
    usable = usable_weather_hours(weather)
    epochs = analog.series_epochs(weather.times)
    names = ["physics", "residual", "current"]
    if variants:
        names += [
            "exploratory watts",
            "exploratory azimuth",
            "exploratory ratios",
            "exploratory ratios azimuth",
            "exploratory vertical",
            "exploratory vertical current",
        ]
    hardware_max_w = hardware_power_limit_w(config.layout, config.inverter_max_w)
    scores = {
        name: {band: {"n": 0, "abs_w": 0.0, "pred_kwh": 0.0, "truth_kwh": 0.0} for band in BANDS + ["total"]}
        for name in names
    }
    origins = []
    skipped = []
    day = first_day.astimezone(config.timezone)
    while day < end_day:
        now = day.replace(hour=6)
        now_ms = now.timestamp() * 1000
        cutoff = (now - timedelta(days=LEARN_DAYS)).timestamp() * 1000
        history = [
            b
            for b in buckets
            if b.end_ms <= now_ms
            and b.start_ms >= cutoff
            and b.start_ms in measured
            and b.start_ms in usable
            and not getattr(b, "curtailed", False)
            and not implausible_hour(b.kwh, b.start_ms, b.end_ms, config.layout.total_kwp)
        ]
        # Count distinct valid hours, so duplicate input cannot manufacture sufficient history.
        history = list({b.start_ms: b for b in history}.values())
        if len(history) < 240:
            skipped.append(day.date().isoformat())
            day += timedelta(days=1)
            continue
        inp = SkyResidualInput(
            lat=config.lat,
            lon=config.lon,
            layout=config.layout,
            production=history,
            inverter_max_w=config.inverter_max_w,
            cloud_times=epochs,
            cloud=weather.cloud,
            shortwave=weather.shortwave,
            direct=weather.direct,
            diffuse=weather.diffuse,
            temp=weather.temp,
            wind=weather.wind,
            snow=weather.snow,
            now_ms=now_ms,
        )
        sky = build_sky_residual_map(inp)
        end = day + timedelta(days=1)
        base = build_forecast_series(
            weather,
            config.layout,
            config.lat,
            config.lon,
            inverter_max_w=config.inverter_max_w,
            start=day,
            end=end,
            step_minutes=15,
            residual_map=sky,
        )
        library = build_library(history, weather, config.lat, config.lon, config.layout, config.inverter_max_w)
        series = {
            "physics": [replace(p, pv_w=p.pv_raw_w) for p in base],
            "residual": base,
            "current": enrich_points(base, library, weather, config.lat, config.lon, now, hardware_max_w),
        }
        if variants:
            watts = build_library(history, weather, config.lat, config.lon)
            ratios = ratio_library(library)
            az = dict(az_weight=0.7, az_norm=90.0)
            vbase = build_forecast_series(
                weather,
                config.layout,
                config.lat,
                config.lon,
                inverter_max_w=config.inverter_max_w,
                start=day,
                end=end,
                step_minutes=15,
                residual_map=vertical_map(inp),
            )
            series.update(
                {
                    "exploratory watts": enrich_variant(base, watts, weather, epochs, now, config=config),
                    "exploratory azimuth": enrich_variant(base, watts, weather, epochs, now, config=config, **az),
                    "exploratory ratios": enrich_variant(
                        base, ratios, weather, epochs, now, config=config, ratio_lib=True
                    ),
                    "exploratory ratios azimuth": enrich_variant(
                        base, ratios, weather, epochs, now, config=config, ratio_lib=True, **az
                    ),
                    "exploratory vertical": vbase,
                    "exploratory vertical current": enrich_points(
                        vbase, library, weather, config.lat, config.lon, now, hardware_max_w
                    ),
                }
            )
        for name, points in series.items():
            points = [limit_forecast_power(p, hardware_max_w) for p in points]
            result = score_points(points, measured, config, now, usable)
            for band, values in result.items():
                for key, value in values.items():
                    scores[name][band][key] += value
        origins.append(
            {
                "date": day.date().isoformat(),
                "training_hours": len(history),
                "latest_training_end_ms": max(b.end_ms for b in history),
                "origin_ms": now_ms,
            }
        )
        day = end
    return {
        "scores": scores,
        "origins": origins,
        "skipped_history_days": skipped,
        "band_coverage": None,
        "scope": "retrospective archived-weather learning replay",
    }


def print_report(result, config):
    print(result["scope"])
    print("Hourly daylight score after 06:00 local; measured zero included; incomplete evidence excluded.")
    print("Matched hours only; archived weather is retrospective, not original issued forecast evidence.")
    print("P10/P90 coverage omitted: hourly energy cannot validate instantaneous power quantiles.")
    for name, bands in result["scores"].items():
        total = bands["total"]
        n = total["n"]
        if not n:
            print(f"{name}: no matched hours")
            continue
        nmae = total["abs_w"] / n / config.layout.total_kwp
        delta = total["pred_kwh"] - total["truth_kwh"]
        print(f"{name}: n={n}, nMAE={nmae:.2f} W/kWp, matched energy error={delta:+.3f} kWh")
    print(f"History-gated dates skipped: {len(result['skipped_history_days'])}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--end-date", help="exclusive local YYYY-MM-DD; default today")
    parser.add_argument("--variants", action="store_true", help="include uncalibrated exploratory variants")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    if args.days <= 0:
        parser.error("--days must be positive")
    try:
        config = ReplayConfig.load(args.config)
        end = datetime.fromisoformat(args.end_date) if args.end_date else datetime.now(config.timezone)
        end = end.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=config.timezone)
        metadata_path = args.data_dir / "metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
            if (metadata.get("entry_id"), metadata.get("production_statistic")) != (
                config.entry_id,
                config.production_statistic,
            ):
                raise ValueError("export metadata does not match configured entry and production statistic")
        result = run_replay(
            load_weather(args.data_dir),
            load_production(args.data_dir),
            config,
            end - timedelta(days=args.days),
            end,
            variants=args.variants,
        )
        print_report(result, config)
        if args.json_output:
            args.json_output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        if not result["scores"]["current"]["total"]["n"]:
            print("No scoreable observations; supply sufficient history and overlapping valid inputs.", file=sys.stderr)
            return 2
        return 0
    except (ValueError, KeyError, TypeError, OSError) as err:
        parser.error(str(err))


if __name__ == "__main__":
    raise SystemExit(main())

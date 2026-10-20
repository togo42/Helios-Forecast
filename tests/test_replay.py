"""Offline replay uses the real model without Home Assistant or network."""

import json
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from custom_components.helios_forecast.forecast import ForecastPoint
from custom_components.helios_forecast.openmeteo import WeatherSeries
from custom_components.helios_forecast.solar.power import PanelOrientation, PvLayout
from custom_components.helios_forecast.solar.residual import ProductionBucket
from tools.replay import replay

UTC = timezone.utc
END = datetime(2026, 6, 15, tzinfo=UTC)


def synthetic_inputs():
    """Fictitious small roof with 14 days of hourly observations and one weather boundary."""
    start = datetime(2026, 6, 1, tzinfo=UTC)
    times = [start + timedelta(hours=i) for i in range(15 * 24)]
    weather = WeatherSeries(
        times=times,
        cloud=[20.0] * len(times),
        shortwave=[500.0] * len(times),
        direct=[350.0] * len(times),
        diffuse=[150.0] * len(times),
        temp=[20.0] * len(times),
        wind=[5.0] * len(times),
        snow=[0.0] * len(times),
    )
    buckets = [ProductionBucket(t.timestamp() * 1000, (t + timedelta(hours=1)).timestamp() * 1000, 0.5) for t in times]
    config = replay.ReplayConfig(
        50.0, 0.0, ZoneInfo("UTC"), PvLayout([PanelOrientation(25.0, 180.0)], [1.0], [None], 3.0, [400.0]), 500.0
    )
    return weather, buckets, config


def test_replay_real_pipeline_smoke(monkeypatch):
    weather, buckets, config = synthetic_inputs()
    histories = []
    original = replay.build_sky_residual_map

    def record_history(inp):
        assert inp.inverter_max_w == 500.0
        assert all(b.end_ms <= inp.now_ms for b in inp.production)
        histories.append(inp.production)
        return original(inp)

    monkeypatch.setattr(replay, "build_sky_residual_map", record_history)
    result = replay.run_replay(weather, buckets, config, END - timedelta(days=1), END, variants=True)
    current = result["scores"]["current"]["total"]
    assert current["n"] > 0
    assert current["pred_kwh"] > 0
    assert current["pred_kwh"] <= current["n"] * 0.4  # per-line cap survives analog refinement
    assert all(scores["total"]["n"] == current["n"] for scores in result["scores"].values())
    assert histories and len(histories[0]) >= 240
    assert result["origins"][0]["latest_training_end_ms"] <= result["origins"][0]["origin_ms"]
    assert result["band_coverage"] is None


def test_zero_is_scored_but_missing_invalid_partial_and_night_are_not():
    _, _, config = synthetic_inputs()
    hour = datetime(2026, 6, 14, 12, tzinfo=UTC)
    ms = int(hour.timestamp() * 1000)
    points = [ForecastPoint(hour + timedelta(minutes=15 * i), 1000.0, 1000.0, 10.0, 2000.0) for i in range(4)]
    now = hour.replace(hour=6)
    valid = {ms}
    zero = replay.score_points(points, {ms: 0.0}, config, now, valid)["total"]
    assert zero == {"n": 1, "abs_w": 1000.0, "pred_kwh": 1.0, "truth_kwh": 0.0}
    assert replay.score_points(points, {}, config, now, valid)["total"]["n"] == 0
    assert replay.score_points(points[:3], {ms: 0.0}, config, now, valid)["total"]["n"] == 0
    assert replay.score_points(points, {ms: 0.0}, config, now, set())["total"]["n"] == 0
    assert replay.score_points(points, {ms: 0.0}, config, hour + timedelta(hours=1), valid)["total"]["n"] == 0
    buckets = [ProductionBucket(ms, ms + 3_600_000, v) for v in [None, -1, float("nan"), float("inf")]]
    assert replay.measured_map(buckets) == {}
    assert replay.measured_map([ProductionBucket(ms, ms + 3_600_000, 0)]) == {ms: 0}


def test_history_gate_counts_unique_valid_covered_hours():
    weather, buckets, config = synthetic_inputs()
    result = replay.run_replay(weather, buckets[-20:] * 20, config, END - timedelta(days=1), END)
    assert result["origins"] == []
    assert len(result["skipped_history_days"]) == 1
    assert result["scores"]["current"]["total"]["n"] == 0


def test_loader_keeps_missing_weather_and_rejects_invalid_production(tmp_path):
    hour = int(END.timestamp() * 1000)
    (tmp_path / "weather.json").write_text(
        json.dumps(
            {
                "cloud_cover": [[hour, 0.0], [hour + 3_600_000, None]],
                "ghi": [[hour, 0.0]],
                "temperature": [[hour, -5.0]],
            }
        )
    )
    weather = replay.load_weather(tmp_path)
    assert weather.cloud == [0.0, None]
    assert weather.shortwave == [0.0, None]
    assert weather.temp == [-5.0, None]
    assert weather.wind == [None, None]
    assert replay.usable_weather_hours(weather) == set()
    (tmp_path / "production.json").write_text(
        json.dumps([[hour, hour + 3_600_000, 0], [hour + 3_600_000, hour + 7_200_000, None]])
    )
    assert len(replay.load_production(tmp_path)) == 1
    (tmp_path / "production.json").write_text(json.dumps([[hour, hour + 900_000, 0.1]]))
    with pytest.raises(ValueError, match="one-hour"):
        replay.load_production(tmp_path)


def test_config_resolves_multi_array_layout_and_rejects_partial_coordinates(tmp_path):
    raw = {
        "entry_id": "ENTRY_A",
        "production_statistic": "sensor.pv_energy",
        "latitude": 0,
        "longitude": 0,
        "timezone": "UTC",
        "arrays": [
            {"kwp": 1, "tilt_deg": 10, "azimuth_deg": 90, "inverter_max_w": 500},
            {"kwp": 3, "tilt_deg": 20, "azimuth_deg": 270, "latitude": 1, "longitude": 2},
        ],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(raw))
    config = replay.ReplayConfig.load(config_path)
    assert config.entry_id == "entry_a"
    assert config.layout.shares == [0.25, 0.75]
    assert config.layout.coords == [None, (1, 2)]
    assert config.layout.total_kwp == 4
    del raw["arrays"][1]["longitude"]
    config_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="together"):
        replay.ReplayConfig.load(config_path)


def test_cli_exports_nonempty_machine_readable_scores(tmp_path):
    weather, buckets, config = synthetic_inputs()
    raw = {
        "entry_id": "fixture",
        "production_statistic": "sensor.fixture_energy",
        "latitude": config.lat,
        "longitude": config.lon,
        "timezone": "UTC",
        "inverter_max_w": config.inverter_max_w,
        "arrays": [{"kwp": 3, "tilt_deg": 25, "azimuth_deg": 180, "inverter_max_w": 400}],
    }
    (tmp_path / "config.json").write_text(json.dumps(raw))
    times = [int(t.timestamp() * 1000) for t in weather.times]
    values = [
        weather.cloud,
        weather.shortwave,
        weather.direct,
        weather.diffuse,
        weather.temp,
        weather.wind,
        weather.snow,
    ]
    (tmp_path / "weather.json").write_text(
        json.dumps({k: list(zip(times, v)) for k, v in zip(replay.WEATHER_FIELDS, values)})
    )
    (tmp_path / "production.json").write_text(json.dumps([[b.start_ms, b.end_ms, b.kwh] for b in buckets]))
    output = tmp_path / "score.json"
    assert (
        replay.main(
            [
                "--config",
                str(tmp_path / "config.json"),
                "--data-dir",
                str(tmp_path),
                "--days",
                "1",
                "--end-date",
                "2026-06-15",
                "--json-output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text())["scores"]["current"]["total"]["n"] > 0
    (tmp_path / "metadata.json").write_text(
        json.dumps({"entry_id": "other", "production_statistic": "sensor.fixture_energy"})
    )
    with pytest.raises(SystemExit):
        replay.main(["--config", str(tmp_path / "config.json"), "--data-dir", str(tmp_path)])


def test_fetch_maps_current_entry_scoped_statistics_without_network():
    if not shutil.which("node"):
        pytest.skip("Node is optional for pure replay; needed only for the HA export CLI")
    source = r"""
        import assert from "node:assert/strict";
        import { weatherStatisticIds, fetchInputs } from "./tools/replay/fetch.mjs";
        const ids = weatherStatisticIds("ENTRY_A");
        assert.equal(ids.ghi, "helios_forecast:entry_a_ghi");
        assert.equal(ids.direct, "helios_forecast:entry_a_direct");
        assert.equal(ids.diffuse, "helios_forecast:entry_a_diffuse");
        assert.equal(Object.keys(ids).length, 7);
        assert.notEqual(ids.ghi, weatherStatisticIds("ENTRY_B").ghi);
        assert.throws(() => weatherStatisticIds(""));
        const requests = [];
        const call = async (message) => {
          requests.push(message);
          if (message.types[0] === "change") return {"sensor.energy": [{start: 0, end: 3600000, change: 0}]};
          return {[ids.ghi]: [{start: 0, mean: 0}], "helios_forecast:entry_b_ghi": [{start: 0, mean: 999}]};
        };
        const result = await fetchInputs({entry_id: "ENTRY_A", production_statistic: "sensor.energy"},
                                         new Date(0), new Date(3600000), call);
        assert.deepEqual(result.production, [[0, 3600000, 0]]);
        assert.deepEqual(result.weather.ghi, [[0, 0]]);
        assert.deepEqual(result.weather.cloud_cover, []);
        assert.deepEqual(requests[1].statistic_ids, Object.values(ids));
        assert.equal(requests[0].units.energy, "kWh");
        assert.equal(result.metadata.entry_id, "entry_a");
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_real_pipeline_zero_observation_changes_score_without_changing_training():
    weather, buckets, config = synthetic_inputs()
    hour = END - timedelta(hours=12)
    ms = hour.timestamp() * 1000
    zero_buckets = [replace(b, kwh=0.0) if b.start_ms == ms else b for b in buckets]
    missing_buckets = [b for b in buckets if b.start_ms != ms]
    zero = replay.run_replay(weather, zero_buckets, config, END - timedelta(days=1), END)
    missing = replay.run_replay(weather, missing_buckets, config, END - timedelta(days=1), END)
    assert zero["origins"] == missing["origins"]
    assert zero["scores"]["current"]["total"]["n"] == missing["scores"]["current"]["total"]["n"] + 1
    assert zero["scores"]["current"]["total"]["truth_kwh"] == missing["scores"]["current"]["total"]["truth_kwh"]
    assert zero["scores"]["current"]["total"]["abs_w"] > missing["scores"]["current"]["total"]["abs_w"]


def test_config_rejects_overflowed_total_capacity(tmp_path):
    raw = {
        "entry_id": "fixture",
        "production_statistic": "sensor.energy",
        "latitude": 0,
        "longitude": 0,
        "timezone": "UTC",
        "arrays": [{"kwp": 1e308, "tilt_deg": 0, "azimuth_deg": 0}, {"kwp": 1e308, "tilt_deg": 0, "azimuth_deg": 0}],
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="total_kwp"):
        replay.ReplayConfig.load(path)

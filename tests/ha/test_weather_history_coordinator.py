"""Weather history integration and related RC2 coordinator boundary regressions."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.helios_forecast import coordinator as mod
from custom_components.helios_forecast.checkup import check_consumption_coverage
from custom_components.helios_forecast.consumption import ConsumptionProfile
from custom_components.helios_forecast.const import DOMAIN
from custom_components.helios_forecast.solar.residual import ProductionBucket

from _weather import make_weather_series

pytestmark = pytest.mark.usefixtures("recorder_mock")


@pytest.fixture(autouse=True)
def no_unrelated_archive_writes(monkeypatch):
    """Archive serialization has dedicated tests; these assert coordinator boundaries."""
    monkeypatch.setattr(mod, "async_add_external_statistics", lambda *_args: None)


def coordinator(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, entry_id="history_test")
    entry.add_to_hass(hass)
    return mod.HeliosForecastCoordinator(hass, entry)


async def test_history_reuses_after_refresh_and_restart_but_cold_outage_fails(hass, monkeypatch):
    instance = coordinator(hass)
    now = dt_util.utcnow()

    async def fetch(_session, _lat, _lon, *, past_days, forecast_days):
        return make_weather_series(now, past_days=past_days, forecast_days=forecast_days)

    request = AsyncMock(side_effect=fetch)
    monkeypatch.setattr(mod, "fetch_weather", request)
    await instance.async_refresh()
    await instance.async_refresh()
    assert instance.last_update_success
    assert [c.kwargs["past_days"] for c in request.call_args_list] == [60, 1]
    revived = mod.HeliosForecastCoordinator(hass, instance.entry)
    await revived.async_refresh()
    assert revived.last_update_success
    assert request.call_args.kwargs["past_days"] == 1
    assert len(revived.weather_series.times) == 68 * 24
    cold = mod.HeliosForecastCoordinator(hass, instance.entry)
    monkeypatch.setattr(mod, "fetch_weather", AsyncMock(return_value=None))
    await cold.async_refresh()
    assert not cold.last_update_success
    assert cold.weather_series is None


async def test_changed_location_cannot_reuse_previous_site_after_failure(hass, monkeypatch):
    instance = coordinator(hass)
    monkeypatch.setattr(mod, "fetch_weather", AsyncMock(return_value=make_weather_series(dt_util.utcnow())))
    await instance.async_refresh()
    assert instance.last_update_success
    hass.config.latitude += 1
    monkeypatch.setattr(mod, "fetch_weather", AsyncMock(return_value=None))
    await instance.async_refresh()
    assert not instance.last_update_success


async def test_optional_store_failures_do_not_discard_real_weather(hass, monkeypatch):
    instance = coordinator(hass)
    monkeypatch.setattr(instance._weather_store, "async_load", AsyncMock(side_effect=OSError("unreadable")))
    monkeypatch.setattr(instance._weather_store, "async_save", AsyncMock(side_effect=OSError("full")))
    monkeypatch.setattr(mod, "fetch_weather", AsyncMock(return_value=make_weather_series(dt_util.utcnow())))
    await instance.async_refresh()
    assert instance.last_update_success


async def test_unified_energy_sources_missing_evidence_clears_last_good_profile(hass, monkeypatch):
    instance = coordinator(hass)
    now = dt_util.now()

    class Manager:
        data = {
            "energy_sources": [{"type": "grid", "stat_energy_from": "sensor.import", "stat_energy_to": "sensor.export"}]
        }

    monkeypatch.setattr("homeassistant.components.energy.async_get_manager", AsyncMock(return_value=Manager()))
    bucket = ProductionBucket(now.timestamp() * 1000, (now + timedelta(hours=1)).timestamp() * 1000, 1)
    fetch = AsyncMock(return_value=[bucket])
    monkeypatch.setattr(instance, "_fetch_change_buckets", fetch)
    assert await instance._consumption_profile_for(now) is not None
    assert {c.args[0] for c in fetch.call_args_list} == {"sensor.import", "sensor.export"}
    fetch.side_effect = [[bucket], []]
    assert await instance._consumption_profile_for(now + timedelta(hours=1)) is None
    assert instance.consumption_coverage == {"sensor.import": 1, "sensor.export": 0}
    assert check_consumption_coverage(instance.consumption_coverage)[0].key == "consumption_source_missing"
    fetch.side_effect = [[], []]
    assert await instance._consumption_profile_for(now + timedelta(hours=2)) is None
    assert instance.consumption_coverage == {"sensor.import": 0, "sensor.export": 0}
    assert len(check_consumption_coverage(instance.consumption_coverage)) == 2


async def test_consumption_transport_failure_preserves_previous_profile_and_coverage(hass, monkeypatch):
    instance = coordinator(hass)
    previous = ConsumptionProfile({}, {}, 100, 1, {"sensor.import": 1})
    instance._consumption_profile = previous
    instance._consumption_coverage = dict(previous.coverage)

    class Manager:
        data = {"energy_sources": [{"type": "grid", "stat_energy_from": "sensor.import"}]}

    monkeypatch.setattr("homeassistant.components.energy.async_get_manager", AsyncMock(return_value=Manager()))
    monkeypatch.setattr(instance, "_fetch_change_buckets", AsyncMock(side_effect=RuntimeError("offline")))
    assert await instance._consumption_profile_for(dt_util.now()) is previous
    assert instance.consumption_coverage == {"sensor.import": 1}

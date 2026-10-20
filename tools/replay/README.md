# Offline learning replay

Replay rebuilds the real residual map and analog library at **06:00 local** for each
past date, then scores that date's subsequent daylight hours against measured energy.
It runs without Home Assistant or network after input export. The normal pure pytest
suite includes a deterministic synthetic replay that exercises the actual model.

The weather input is the integration's **retrospective hourly archive**. It can have
been corrected or backfilled after the evaluation origin. This experiment isolates
learning conditional on that archived weather; it does **not** recreate the original
issued forecasts, prove forecast accuracy as known at the time, or calibrate P10/P90.
Production is cut off at each evaluation origin; no later production trains that date.

## Explicit local configuration

Create a private JSON file, for example `dist/replay/config.json`. The following is a
fictitious configuration; replace it with the chosen entry's actual settings. No roof,
coordinates, entity name, host, token or timezone is hardcoded in the reusable CLI.
`entry_id` is the integration's **config entry ID**, not its title or an entity ID.
`production_statistic` must be a cumulative production-energy statistic supporting
hourly `change`, convertible to kWh (not a power sensor).

```json
{
  "entry_id": "YOUR_CONFIG_ENTRY_ID",
  "production_statistic": "sensor.your_production_energy",
  "latitude": 0.0,
  "longitude": 0.0,
  "timezone": "UTC",
  "inverter_max_w": 2000,
  "arrays": [
    {"kwp": 2.0, "tilt_deg": 25, "azimuth_deg": 180, "inverter_max_w": 1500},
    {"kwp": 1.0, "tilt_deg": 25, "azimuth_deg": 270}
  ]
}
```

Each line uses `kwp`, `tilt_deg`, `azimuth_deg` and optional `tracker`,
`inverter_max_w`, `latitude` and `longitude` (coordinates supplied together).
Line kWp values determine shares and total kWp. An omitted/null cap is unbounded;
the entry cap and configured line caps are respected by the physical model and by
final analog output. `tracker` accepts `dual-axis`, `single-axis-h`, `single-axis-v`
or null. Optional learning gates, curtailment/SoC history, strict input provenance
and other runtime entry options are **not** reconstructed. Check production quality
before interpreting results, especially when curtailment is possible.

## Export once, replay offline

Export requires Node 22+ with its built-in WebSocket. Set `HA_URL` to the chosen HA
HTTP(S) origin and `HA_TOKEN` privately in the environment. The exporter issues only
Recorder statistics reads. It selects these integration-owned statistics for the
configured entry, lowercasing the entry ID:

```text
helios_forecast:<entry_id>_{cloud_cover,ghi,direct,diffuse,temperature,wind_speed,snow_depth}
```

Retired `sensor.helios_forecast_*` mean statistics and other entries are not selected.
Use a fresh output directory; existing input files are refused. Data and configuration
under ignored `dist/` stay outside Git and provider review payloads.

```sh
node tools/replay/fetch.mjs --config dist/replay/config.json \
  --data-dir dist/replay/export-1 --days 75 --end 2026-06-15T00:00:00Z
python tools/replay/replay.py --config dist/replay/config.json \
  --data-dir dist/replay/export-1 --days 30 --end-date 2026-06-15 \
  --json-output dist/replay/result.json
```

The replay needs Python 3.13 with repository imports available; no HA installation or
extra runtime packages are required. `--end-date` is an **exclusive local date** and
defaults to today in the configured timezone. `--days` counts local calendar dates.
Fetch `--days` counts elapsed 24-hour days. Include at least ten days of earlier valid
history plus the evaluation window and an extra weather boundary hour. With sparse
archives, fetch more. Without at least **240 distinct valid hourly production/weather
pairs** in the preceding learning window, that date is skipped. The residual and analog
learners retain their own support gates and may fall back to physical output.
A CLI run with no scoreable observations exits 2; it never presents an empty run as a
successful accuracy result. Export metadata, when present, must match the configured
entry and production statistic.

Files are plain JSON:

- `production.json`: `[[start_epoch_ms, end_epoch_ms, change_kwh], ...]`.
- `weather.json`: an object keyed by the seven suffixes above, each containing
  `[[start_epoch_ms, mean], ...]`.
- `metadata.json`: export entry, production statistic, requested range, fetch time
  and retrospective-weather label. It contains no token or host.

Only UTC-aligned one-hour meter buckets are supported. Negative resets, non-finite
or missing observations are excluded; conflicting duplicate observations fail.
Weather missing values stay null. Scoreable hours require adjacent real cloud and
irradiance samples and all four forecast quarter-hours, so gaps are excluded rather
than silently extended or filled with sunny defaults. Zero cloud, zero irradiance and
**valid measured daylight zero production remain real observations**. Implausible
production above the model's panel-size guard is excluded from learning and scoring.
This stacked package does not include the separately proposed clock-change fix.
Clock-change-day behavior still depends on upstream forecast assembly; complete-hour
matching rejects incomplete or duplicated groups rather than inventing observations.

## Interpretation

The default compares physical output, residual-only output and the current integration
pipeline. Results include matched-hour counts, nMAE in W/kWp and signed energy error
**over those matched hours**, plus scores by solar-altitude group in JSON. These are not
whole-day energy errors when evidence is incomplete. Hourly kWh truth is compared with
the average of the four quarter-hour power buckets. No P10/P90 coverage is reported:
instantaneous power quantiles cannot be validated against hourly energy, and taking
`min(P10)`/`max(P90)` would create an unjustified hourly envelope.

`--variants` retains exploratory watts, azimuth, ratio and vertical-smoothing alternatives.
They are research comparisons, have no calibration claim, and do not change runtime
learning settings. Their final outputs use the same hardware bound. The default current
pipeline uses the integration's real library/enrichment functions, not a copied learner.

# RC2 upstream preparation

These are separate local committed snapshots, `implemented_pending_review` until
the coordinator completes the mandatory reviews. They contain no fork release,
governance, site configuration, weather-history cache or grid-parser changes.
Upstream develop was frozen at `c5fff9d479605c38b2d72031cbf82b283ef4814d`.
Existing PR heads and upstream grid PR #86 are unchanged.

## Hardware bounds

- Branch: `feature/final-hardware-limits-rc2`.
- Base: `c5fff9d479605c38b2d72031cbf82b283ef4814d`.
- Target: `036c1a64455391e48d6e3a33f777e1d11a9e1d6a`.
- Tree: `bd6d868599b589e56c4e0c9ed926fb5ca9303a6b`.
- Files: analog.py, forecast.py, coordinator.py, a pure hardware-limit test and a
  focused HA coordinator wiring test. No preexisting fork DST delta is copied.
- Validation on this isolated target: 27 focused pure tests, 257 complete pure
  tests and two HA wiring cases passed. Changed-file Ruff/format and whitespace
  checks passed.

PR title: **Keep configured inverter limits after analog forecast refinement**.

Analog refinement can undo the physical model's inverter clipping: a deterministic
regression produces 6300 W from a physically clipped 4500 W point when the learned
ratio is 1.4. Apply the configured hardware bound after analog refinement so final
point forecasts and existing bands obey the entry/combined line caps on live,
elapsed/card and reconstructed archive paths. An uncapped line leaves its part
unbounded. Raw physics remains the ratio reference, the learning formula remains,
and null bands remain null. This is a bounded correctness repair, not evidence of
forecast accuracy or quantile calibration.

The coordinator may open this narrowly scoped upstream draft after the strict
target-specific review receipts pass. Its target branch is develop-2026.10.0.

## Replay follow-up

- Branch: `feature/replay-repair-rc2`.
- Incremental base: `036c1a64455391e48d6e3a33f777e1d11a9e1d6a`.
- Target: `aed361a2d387ada8a80c13dd8fd78aa68350575d`.
- Tree: `433c777bffa26c58819a4d52aa23c21345079bbc`.
- Incremental files: four tools/replay files and tests/test_replay.py.
- Validation on this target: nine replay tests and 266 complete pure tests passed;
  changed-file Ruff/format, Node syntax and whitespace checks passed.

PR title: **Repair offline replay inputs, archive export and matched-hour scoring**.

The current replay omits the required inverter limit and exports retired sensor
mean IDs. Restore the real pipeline with explicit local entry/layout/timezone
configuration and current integration-owned weather IDs. Preserve missing input,
score measured daylight zero production, require complete matching hourly evidence,
and fit only on production available at each 06:00 evaluation origin. Apply the
hardware-bound API from the prerequisite branch. Report matched-hour energy/nMAE,
without unsupported instantaneous-band calibration. Archived weather is retrospective
and isolates learning; it does not reconstruct original issued forecast skill.

Prepare this PR against the fork hardware branch first. Only after that prerequisite
is merged upstream should a refreshed replay branch target upstream develop, with
new tests and reviews. The separate existing upstream DST proposal is not included;
the upstream replay README explicitly preserves that limitation. The mandatory
review of this pushed target covers the complete cumulative develop-to-target
range, including its prerequisite hardware code.

## Weather and grid follow-ups

The basic unified grid parser is already proposed upstream in PR #86; no duplicate
submission is made. Missing-consumption evidence is a separately prepared fork
extension and is not silently added to that author's PR. Weather history currently
uses the fork's existing optional provenance contract and receipt-aware transport;
its upstream transfer needs those prerequisites resolved and is not represented as
an independent ready-to-merge patch against current upstream develop.

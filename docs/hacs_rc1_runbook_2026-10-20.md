# Conditional HACS rc1 migration runbook (2026-10-20)

Permanent working root: `/home/tg/Helios-Forecast`. The user's latest authorization
is conditional: only after successful Gemini full/meta review, independent gates
and exact-commit CI may the coordinator merge PR #7 at
`a8ba20b2257cc7a747542fc45c08528273f0f664`, integrate the reviewed policy and
switch HA to the immutable candidate. A runtime defect found in review stops this
migration. Never replace the published tag or asset; corrections need a new version.

Before migration, create and verify a full Home Assistant backup explicitly
including Recorder: `ha backups new --homeassistant-exclude-database=false` via
the authorized SSH path. Existing automatic backups exclude the database and do
not satisfy this gate. Record backup identity, size and SHA-256. Preserve the
actual installed overlays, not merely stock 2026.9.6. Save a private inventory of
the current 67 code files, four config entries, 148 entities (99 disabled), eight
learned files and 36 Recorder series; fresh readback must confirm these counts.

Only HACS source ownership changes: add the fork and remove the upstream code
source. Never delete HA config entries: `async_remove_entry` destroys archive and
learned data. Download exactly `v2026.10.0rc1`; the candidate ZIP SHA-256 is
`4fe6e5be5826e938a36dde019f3d426434b3af559a2f6f33e55bad6b4dc795ba`.
Verify every one of the target's 68 files against that asset and remove obsolete
code only after backup; do not leave a mixed overlay. Before restart, compare
config entries, registries and learned files for exact preservation, then perform
the supported configuration check and separately authorized Core restart.

Read back all four loaded entries, stable services and payload shapes, new logs,
Recorder/archive extent, registry settings and learned state. HACS must show the
fork as the only installed source at the fixed rc1 version. Stop and restore the
recorded actual previous code/source/version on failure; preserve entries and
learned state. If later state becomes incompatible, use the complete matching
backup rather than deleting storage keys.

Private operational snapshots/readbacks remain in ignored `dist/` or private
storage and must never enter Gemini payloads. The coordinator reports the actual
outcome in a JSON receipt and chat. This runbook records conditional authorization;
it does not claim that migration has happened. No ESS consumer/control activation
or synthesized native P10 forecast is authorized here.

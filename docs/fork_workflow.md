# Fork development and release workflow

`togo42/Helios-Forecast` is an independently maintained fork of
`ReikanYsora/Helios-Forecast`. Original attribution and GPL-3.0 LICENSE remain.
General fixes are prepared as separate feature pull requests; installation-specific
adapters and control policies belong outside this integration.

## Branches and remotes

- `origin`: `https://github.com/togo42/Helios-Forecast.git`, the default push remote.
- `upstream`: `https://github.com/ReikanYsora/Helios-Forecast.git`.
- `main`: unmodified upstream mirror, currently
  `76d305ebfced57fe254a6f1553404337d8e2fff1`.
- `fork/stable`: curated fork line; the reviewed combined behavioral baseline is
  `ce2838fe79cf1fda306ad853e8f102b91b2cc364`.
- `release/2026.10.0rc1`: first candidate, prepared from that baseline.

Upstream develop was observed at `c5fff9d479605c38b2d72031cbf82b283ef4814d`;
later upstream changes are excluded. The separate DST/refresh contributions and
internal cache/provenance/strict-learning PRs stay unchanged. Do not bulk merge
develop or those PR branches into the release.

For subsequent work, fetch without changing a working branch:

```sh
git fetch upstream --prune
```

In a clean checkout of `main`, advance the mirror only with
`git merge --ff-only upstream/main`; stop on divergence. Create each `feature/*`
branch from the explicitly selected upstream base, keep its general fix separate,
and open an upstream PR from that feature branch after its own gates. Curate
`fork/stable` through a dedicated integration branch with named, reviewed and
tested changes; use targeted checked cherry-picks or equivalent explicit
integration. Do not blanket-merge upstream develop or all open feature PRs.
Prepare `release/*` from that curated result and complete acceptance/review gates
before advancing release references or publishing. No command in this workflow
authorizes an automatic merge, push, tag or HA rollout.

Once published, integrate `fork/stable` only forward; do not rebase it or force
push it. Never replace published tags or release assets: corrections receive a
new version. Keep a general test-fixture correction as a separate upstream
follow-up to the existing refresh contribution; do not silently change its
existing PR head or publish a duplicate PR. Manufacturer integration stays a
separate decision.

## Build and verify

Use Python 3.13 and Git. Commit the approved delivery first, then replace PIN
below with its full 40-character commit SHA. These commands do not create tags,
publish assets, change branches, contact GitHub or install anything:

```sh
python3 scripts/build_fork_release.py build --expected-rev PIN \
  --version 2026.10.0rc1 --tag v2026.10.0rc1 --output dist/rc1
python3 scripts/build_fork_release.py verify --expected-rev PIN \
  --version 2026.10.0rc1 --tag v2026.10.0rc1 --output dist/rc1
```

The pinned revision must equal HEAD and the repository must have no tracked or
untracked changes. Ignored Python bytecode caches are excluded; other ignored
integration inputs fail. `dist/` is ignored. Existing output directories fail
instead of being reused. An existing tag must resolve to the pinned commit;
before publication the receipt records the intended tag without creating it.

The ZIP contains every tracked regular file in
`custom_components/helios_forecast/`, with that prefix removed. Entries are sorted,
uncompressed, timestamped 1980-01-01 and mode 100644. Symlinks, submodules and
unsafe paths fail. No repository documents, tests, replay tools, untracked site
configuration, caches or learned state enter this runtime tree. Verify compares
every ZIP member with the Git blob and requires canonical ZIP and receipt bytes.
The separate `release-receipt.json` binds revision, intended tag, version, archive
SHA-256 and each member's SHA-256. It is not installed into the integration.

## HACS and publication gates

The candidate's `hacs.json` identifies the fork, hides the default branch and
selects `helios_forecast.zip`. HACS extracts release ZIPs directly into
`custom_components/<domain>`; therefore the ZIP's root contains `manifest.json`,
not a wrapping `custom_components/helios_forecast` directory. Read-only HA
inventory on 2026-10-20 reported HACS **2.0.5**. Source checked on that date at
tag `2.0.5`, commit `c0dfd8b44297c3673c21973e2539375a53687a9c`:
[HACS base repository downloader](https://github.com/hacs/integration/blob/c0dfd8b44297c3673c21973e2539375a53687a9c/custom_components/hacs/repositories/base.py)
(`async_download_zip_file`, `async_get_hacs_json`) and
[integration localpath](https://github.com/hacs/integration/blob/c0dfd8b44297c3673c21973e2539375a53687a9c/custom_components/hacs/repositories/integration.py).
[HACS metadata documentation](https://hacs.xyz/docs/publish/start/) describes
`zip_release`, `filename` and `hide_default_branch`.

HACS reads metadata via `ref or version_to_download()`, so installation at an
explicit release selection uses that release's metadata. The unchanged mirror's
metadata cannot advertise fork restrictions when users explicitly select main.
Do not claim every HACS discovery/UI path has been exercised: this is source
inspection, not a live HACS installation. Before publication, check selected-tag
metadata, manifest and the exact release asset URL without writing to HA. HACS
2.0.5's `show_beta` selection must permit prereleases; explicitly select the fixed
candidate version. Do not use the default branch as a replacement for that
release. A real HACS UI installation/readback remains a later separately
authorized HA rollout gate, not a prerequisite requiring productive writes now.

Run the complete pure and Home Assistant suites, pinned Ruff lint/format and mypy,
independent behavioral acceptance and final external review against the frozen
baseline. Record exact pins and hashes after gates. Publication is a separate
coordinator step: create the fixed `v2026.10.0rc1` GitHub prerelease with both
verified files, do not mark it latest/stable, and verify GitHub checks on that
exact commit. No publication workflow or write permission was added. A release or
merge does not grant productive rollout permission.

## Migration and rollback for a later authorized rollout

No rollout is authorized by this candidate. Before a later source switch, make a
verified Home Assistant backup including configuration, `.storage`, recorder and
the existing integration directory; record the currently installed revision and
settings. Do not uninstall the config entry or delete entities, statistics or
learned files. Only one source may own the existing `helios_forecast` directory.
Replace code only after separate approval and leave optional strict learning,
benchmark and battery settings disabled unless already explicitly chosen. Preserve
all existing options and disabled entity settings; this candidate changes no defaults.

On a separately authorized rollback, stop/restart Core through the supported HA
procedure, restore the recorded previous integration code and HACS source/version,
and retain the existing domain, config entries, entity registry, recorder and
learned state. Check that entry and entity IDs, services and archive access match
the saved inventory. If state has been changed by a later incompatible version,
restore the complete matching backup instead of deleting storage keys manually.

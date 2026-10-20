# FORK-RELEASE-01: first reproducible fork candidate

Scope frozen before implementation on 2026-10-20.

## Source and intended result

This fork prepares reusable changes for upstream and offers separately versioned
integration packages for users who choose this fork. General improvements remain
separate feature branches. Installation-specific adapters and control policies
remain outside Helios.

- Original project: `ReikanYsora/Helios-Forecast`.
- Fork: `togo42/Helios-Forecast`.
- Unmodified main mirror: `76d305ebfced57fe254a6f1553404337d8e2fff1`.
- Frozen implementation baseline: `ce2838fe79cf1fda306ad853e8f102b91b2cc364`.
- Observed upstream development head: `c5fff9d479605c38b2d72031cbf82b283ef4814d`.
  Its later changes are not part of this candidate.
- Candidate version: `2026.10.0rc1`, release tag `v2026.10.0rc1`.
  HA's AwesomeVersion and Python packaging both recognize this version, and
  AwesomeVersion orders `2026.9.6 < 2026.10.0rc1 < 2026.10.0`.

Maintain a persistent local clone with `origin` pointing at the fork and
`upstream` at the original project. Local main tracks upstream/main; pushes
default to origin. The own `fork/stable` branch contains curated fork changes.
Prepare the candidate on `release/2026.10.0rc1`, then advance fork/stable only
after the required gates. Existing branches and pull requests remain unchanged.

## Allowed implementation

- Manifest: candidate version and fork documentation/support ownership metadata.
  Preserve integration domain, display name, dependencies and runtime options.
- HACS metadata: clearly identify the fork, hide the development/default branch,
  and describe the exact verified release asset when zip_release is used.
- Existing CI workflows: cover fork/stable and release branches; preserve current
  test depth and permissions. No automatic publication or deployment workflow.
- A minimal offline release build/verify CLI with meaningful tests. Read the
  explicitly pinned committed integration tree, generate a deterministic ZIP and
  SHA-256 receipt, and validate version, revision, paths and content. Fail before
  publication on dirty inputs, mismatch, tampering or output collision.
- README, changelog and docs/: fork workflow, upstream contribution boundaries,
  release notes, verification evidence and a concrete rollback procedure.
- Ignore generated build outputs. Preserve original attribution and LICENSE.

No forecast algorithms, Python files inside custom_components, entity identifiers,
configuration entries, learning storage formats, defaults or controller bindings
may change. No manufacturer pull request, existing PR merge, HA installation,
source switch, runtime capture or restart is part of this task.

## Expectations and gates

1. The release integration payload is byte-identical to the baseline except for
   the explicitly named manifest metadata changes. No private configuration or
   development-only files enter the ZIP.
2. Two builds from the same committed revision produce identical ZIP bytes.
   Every ZIP member matches its pinned Git blob, including required assets.
3. Wrong version/revision, dirty integration inputs, unsafe paths, modified or
   missing payload members, bad hashes and existing output paths fail closed.
4. A clean extraction into an isolated Home Assistant test environment preserves
   service/config-entry behavior. Existing options remain opt-in/off by default.
   This is synthetic compatibility evidence, not a productive installation.
5. Run the complete pure and HA test suites plus the existing lint/format/mypy
   gates. Independent acceptance uses its own calculations and effective
   assertion mutations against the real CLI. Preserve previous acceptance
   harnesses and historical reports.
6. Coordinator pre-review, then external full review of the whole delivery
   against the frozen baseline. Record and assess findings without treating
   reviewer prose as source truth.
7. Bind final branch/tag, revision and asset hashes; verify GitHub checks on the
   exact published candidate. A GitHub prerelease is not a stable or productive
   approval. Do not mark it latest/stable or install it in HA.

The candidate retains the limits of the baseline: no new empirical winter,
DC-constraint, calibrated daily P10 or recovery acceptance is implied.

## Bounded test-fixture amendment before implementation

At 17:01 UTC the inherited hour-rollover test failed identically on the unchanged
base and candidate: advancing from before the entry's scheduled phase also fires
that current-hour event. The test entry's phase is HH:09:23, not a universal HH:07
boundary. Waiting for a wall-clock window would leave CI dependent on invocation
time. Before changing the test, this narrow additional scope is authorized:

- Only `tests/ha/test_init.py::test_hour_rollover_triggers_off_cycle_refresh` may
  gain a controlled freezer fixture/time after its current-hour phase.
- Preserve every original assertion, the two event times and production sources.
  Do not skip, xfail, relax a count or alter scheduler behavior.
- Commit this test fixture fix separately; preserve existing upstream PR heads.
- Verify the original assertion AST is unchanged, run the actual test and full
  HA suite, and independently show a removed hourly listener still causes an
  assertion failure. Preserve the initial failed run and identical-base probes.
- Repeat release/ZIP binding at the final revision. The integration payload and
  builder must remain identical to the accepted implementation freeze.

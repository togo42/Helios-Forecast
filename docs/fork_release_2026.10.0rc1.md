# Fork candidate 2026.10.0rc1

Status: implemented candidate, pending final external review and publication gates. No publication, HA installation, source switch or productive activation
is part of implementation.

The candidate reuses frozen reviewed baseline
`ce2838fe79cf1fda306ad853e8f102b91b2cc364`. Runtime files remain byte-identical
except manifest version `2026.10.0rc1` and fork documentation, issue tracker and
code owner metadata. Domain `helios_forecast`, display name, services, entity IDs,
configuration entries, schemas, learned state and defaults are preserved.

Included baseline changes: elapsed-UTC DST forecast intervals, staggered archive
refresh and bounded weather retry jitter, shared successful weather request cache,
optional forecast provenance, opt-in strict learning quality and upstream
translation placeholder correction. Existing feature branches and PRs remain
separate; upstream develop's later changes are excluded.

This is synthetic/test-only compatibility evidence. There is no productive HA,
empirical winter, DC-constraint, calibrated daily P10 or recovery acceptance.
Native unavailable uncertainty stays unavailable; no synthetic P10 is introduced.
No ESS/control permission follows from this package.

Version ordering was separately checked with Home Assistant's AwesomeVersion and
Python packaging: `2026.9.6 < 2026.10.0rc1 < 2026.10.0`. The tag is
`v2026.10.0rc1`; AwesomeVersion also confirmed tag-prefix equality
`v2026.10.0rc1 == 2026.10.0rc1`. A GitHub prerelease must remain non-latest. Follow
[fork workflow](fork_workflow.md) for exact build/verify, future migration and
rollback procedures. The separate release receipt binds the final committed
revision and member/archive hashes; do not infer those from this document's commit.

## Implementation verification

Runtime/builder implementation freeze:
`ceed94a52388ca95228881614ab367160c552a26`. Two builds and a verify of this
committed tree passed (exit 0); ZIP and receipt repeat comparisons also returned
0. ZIP SHA-256:
`4fe6e5be5826e938a36dde019f3d426434b3af559a2f6f33e55bad6b4dc795ba`.
Receipt SHA-256 at that implementation revision:
`ceddbedb22e80275e39b6381359f242ae1b49b4726acba3b0718612852e9fdf6`.
These files in `dist/rc1-impl/` are ignored local artifacts; final publication
must rebuild/rebind the receipt to the final committed revision. The ZIP payload
remains unchanged by later documentation, evidence and the test-only fixture fix.

Author gates on Python 3.13.11 (paths below identify temporary local test
installations, not durable runtime dependencies):

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/helios-fork-20261020/pure/bin/python -m pytest -q tests --ignore=tests/ha`:
  267 passed including 20 release CLI cases, exit 0 (6.64 s).
- `/tmp/helios-fork-20261020/lint/bin/ruff check custom_components tests scripts`
  and `ruff format --check custom_components tests scripts`: both passed at
  implementation freeze (Ruff 0.15.20, 68 files); the fixture-only follow-up also
  passed targeted Ruff lint/format, exit 0.
- `/tmp/helios-fork-20261020/lint/bin/mypy custom_components/helios_forecast`:
  passed, exit 0 (mypy 1.19.1, 32 runtime files). All inherited HA import-check
  modules imported successfully, exit 0.
- `/tmp/solar-upstream-20261020/ha313/bin/python -m pytest -o asyncio_mode=auto -q tests/ha/test_init.py::test_hour_rollover_triggers_off_cycle_refresh`:
  with the fixture follow-up, 1 passed, exit 0 (11.93 s).
- `/tmp/solar-upstream-20261020/ha313/bin/python -m pytest -o asyncio_mode=auto -n 8 -q tests/ha`:
  with the fixture follow-up, complete 139 passed, exit 0 (122.14 s).

Independent release acceptance is recorded in
[fork release R](fork_release_r_2026-10-20.md): real CLI/Git/ZIP checks, effective
negative mutations and 68-file clean extraction, followed by unchanged historical
34/34 behavioral cases and 3/3 effective assertion mutations on the extracted
payload. Final review remains a separate coordinator gate. CI retains all
inherited jobs and read-only permissions while adding `fork/stable`, `release/**`
and manual invocation; helper lint/format is included.

## Inherited clock-test failure and bounded fixture follow-up

The first unchanged sequential HA invocation (same HA command without `-n 8`)
reported 138 passed and 1 failed in 382.82 s. Its shell wrapper ended with `tail`
and therefore returned 0 without preserving the pytest process exit; that run is
**failed evidence**, never a successful gate. At 17:01 UTC the exact original
hour-rollover test independently failed on both frozen baseline and candidate
(exit 1 each, 14.25 s and 14.61 s), with the same mock already awaited once.
A second unchanged full run with `-n 8`, started 17:07:05 UTC, again reported
138 passed/1 failed, actual exit 1 (115.99 s). Both full failures affected only
`test_hour_rollover_triggers_off_cycle_refresh`.

The test uses `entry_id="test_entry"`, whose unchanged hash-derived refresh phase
is **HH:09:23**. Before that phase, its jump to the next hour also triggers the
current-hour scheduled event. The original non-awaited assertion was therefore
dependent on invocation time. HH:07 was an earlier observation, not the actual
boundary. This is a test-clock problem reproduced on unchanged production code;
it is not a newly introduced runtime bug or evidence of a scheduler repair.

Scope amendment `95e96d73938feb3abf6210b092573d778836308b` authorized the narrow
follow-up before implementation. Separate test-only commit
`95285edb394b55511e88e186a58aca7d4df9a93b` adds the freezer fixture and moves to
`2026-10-20T12:30:00+00:00` before setup. All original assertions, both event-time
expressions and production sources remain unchanged. The successful author gates
above use that fixture. Independent
[clock-fixture R](fork_clock_fixture_r_2026-10-20.md) passed: all 25 original
assertion/mock-assert call ASTs and the normalized entire module AST are preserved;
the real target passes with no skip; removing the hourly listener in a private
mutation still fails at the original `assert_awaited_once` with zero awaits.
Runtime and builder bytes were independently confirmed unchanged.

This general test correction is prepared as a separate follow-up to the existing
refresh contribution. No existing upstream PR head was changed, no duplicate PR
was published, and manufacturer integration remains separate. Temporary raw run
logs under `/tmp/helios-release-*.log` are non-durable; this report and the
independent R reports preserve the results in Git.

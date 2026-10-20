# FORK-RELEASE-01 coordinator pre-review

Date: 2026-10-20. Delivery behavior base:
`ce2838fe79cf1fda306ad853e8f102b91b2cc364`; implementation freeze:
`ceed94a52388ca95228881614ab367160c552a26`.

The coordinator read the complete implementation diff, release helper, CLI tests,
CI workflows, HACS/manifest metadata, README, changelog, scope and workflow notes.
This review is independent of the implementation worker's test assertions.

- Integration payload: only the four allowed manifest metadata fields differ.
  Runtime Python, assets, entity/configuration identity, options, defaults and
  learned-state formats are preserved. No algorithm or consumer contract changes.
- Build/verify: committed Git blobs, full revision and intended tag/version are
  bound; archive membership and file content are checked against those blobs,
  followed by canonical archive/receipt bytes. Paths, symlinks, dirty/untracked
  inputs, ignored non-cache runtime inputs and existing outputs fail closed.
  Stored ZIP entries have sorted names, fixed timestamps and regular-file modes.
  Site data and development files outside the integration tree are excluded.
- HACS: archive root layout matches its release ZIP extraction destination.
  Installed HACS 2.0.5 was read through HA-MCP without mutation; tag 2.0.5 points
  at `c0dfd8b44297c3673c21973e2539375a53687a9c`. Its repository methods select
  metadata by release ref and require explicit prerelease visibility/selection.
  Main's mirrored metadata cannot impose fork restrictions. Full HACS UI/source
  switching remains a separate future rollout check.
- CI: every inherited job remains, permissions stay contents:read, and the new
  helper is linted. New branch patterns cover curated/release branches. No
  automatic publication, elevated Actions permissions or production deployment.
- Repository/support: original attribution and GPL-3.0 LICENSE remain. Own public
  fork's issue tracker is enabled. Existing PR heads and upstream remain outside
  this delivery; no blanket development merge is proposed.
- Role, topology, protected fields, logging, dashboards and flow export: no
  changes or productive effects. Existing forecast limitations remain explicit.

No implementation finding was identified. Documentation follow-up requested:
pin the HACS source check to installed 2.0.5, explain the daily contribution/update
commands, and report actual implementation HA results. Generated local raw review
outputs are ignored; this changes neither release inputs nor runtime behavior.

Independent evidence subsequently supplied and inspected: 17 real release CLI
calls (3 positive, 12 expected failures, 2 deliberately faulty producer calls),
68-file independent Git/archive oracle and 2 effective assertion mutants. The
unchanged historical behavior harness also passed 34 cases and 3 effective
mutants against the literal ZIP-extracted payload, including actual synthetic HA
service/learning probes. Runtime hashes matched before and after those probes.
Read the independent report for its exact pins, hashes and reproduction commands.

The first sequential inherited HA suite returned 138 passed and one failure in
`tests/ha/test_init.py::test_hour_rollover_triggers_off_cycle_refresh`. At 17:01 UTC
the unchanged base and candidate both failed that original test identically
(`Expected mock to not have been awaited`, actual 1). Subsequent source inspection
established the exact test-entry phase as HH:09:23. HH:07 was an imprecise earlier
observation, not its boundary. This is an inherited wall-clock-sensitive test,
not a candidate runtime regression. The scope now permits a separate controlled
freezer-fixture repair with every assertion and production source preserved.
Independent assertion-AST and effective removed-listener checks plus the full HA
suite must validate that repair; results belong in separate candidate/R evidence.

Final external full review and exact-revision GitHub checks remain required
before publication. Their separate evidence must be read with this report.

## Final local gate readback

The dedicated test-only repair is commit
`95285edb394b55511e88e186a58aca7d4df9a93b`: one freezer argument and a fixed
`2026-10-20T12:30:00+00:00` move before setup. The coordinator inspected that
complete diff. Production sources and the release builder remain unchanged.

The author subsequently reported real successful exits for 267 pure tests,
139 full HA tests (`-n8`, unchanged plugin configuration), the targeted rollover
test, and Ruff lint/format. The separate clock-fixture acceptance compared all
25 original assertion/mock-assert call ASTs and the complete test-module AST after
normalizing exactly those two fixture additions. All were identical. Its actual
test passed without skips; removing the hourly listener in a disposable runtime
copy caused the original `assert_awaited_once` to fail with zero awaits. The
runtime inventory/content and builder matched the pre-repair source.

Read `docs/fork_clock_fixture_r_2026-10-20.md` and the candidate evidence for exact
pins, argv, exits and hash binding. These local gates permit review/publication
preparation; they grant no productive installation or empirical acceptance.

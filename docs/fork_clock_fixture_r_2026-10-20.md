# Independent clock-fixture acceptance

Result: PASS for the narrow fixture change in
`95285edb394b55511e88e186a58aca7d4df9a93b`.
The scope was committed before implementation in
`95e96d73938feb3abf6210b092573d778836308b`.

The original hourly rollover test depended on its invocation time. Its entry
phase is HH:09:23; starting before that phase can dispatch a current-hour
scheduled event while advancing to the next hour. A controlled initial time
of `2026-10-20T12:30:00+00:00`, established before integration setup, removes
that ambiguity. The original event expressions still dispatch at the next
hour's 00:05 and its entry-specific 09:23 phase.

Expectations were stated independently before the author froze the test fix.
The independent oracle parses the complete original and candidate test module
with Python's AST and checks the actual HA test in a disposable pinned clone.
It does not reuse author assertions as its only source oracle.

| Independent gate | Result |
| --- | --- |
| All 25 original assertion and mock-assertion call AST nodes | Identical, including counts and order |
| Complete test module after removing exactly one added `freezer` argument and one initial `freezer.move_to` statement | AST identical |
| Initial clock precedes original setup and falls after the entry phase | PASS, 12:30 after 09:23 |
| Integration file inventory, every runtime byte and release builder against the pre-fix scope commit | Identical |
| Actual unchanged target test and original event/assertion logic | 1 passed, 0 skipped, exit 0 |
| Mutation removing only hourly listener registration from a disposable integration source | Original `assert_awaited_once()` fails: awaited 0 times, exit 1 |
| Restore mutation and inspect disposable clone | Original bytes restored, clean worktree |

No skip, xfail, assertion relaxation, event-time expression change, scheduler
change or production source change is part of this fixture fix. The source
mutation was not a candidate change. It proves that the frozen test still
rejects a real missing-listener regression at its original final assertion.
The author separately reports the complete 139-test HA suite passing; the
independent execution here covers the focused fixture and counterexample.

Reproduction from a checkout containing the complete relevant Git history:

```sh
python3 tests/acceptance/clock_fixture_r.py \
  --repo . --expected-rev <full-candidate-commit> \
  --ha-python <existing-home-assistant-test-python> \
  --work <new-disposable-directory>
```

The test environment must already contain the project's original HA test
dependencies and plugins. The oracle retains the original plugin configuration
and asyncio mode. Raw JSON/JUnit results belong in ignored generated outputs.

- Oracle SHA-256: `c05d57a7de4d44dbab44787b3747fee09722f98713dfe8f82ae476067f2b14d0`.
- Independent raw result JSON SHA-256: `efe3feedad42f94373287463f3f26bf9fd749bbbc9b824812922f1609e106fcd`.

This fixture acceptance grants no publication, installation or productive
permission. The earlier literal release-payload behavior result remains bound
to its tested source bytes; the unchanged runtime inventory preserves that
comparison. Final release assets and receipt still need binding to the final
release revision.

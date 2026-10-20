# FORK-RELEASE-01 independent acceptance

Release candidate `2026.10.0rc1`, planned tag `v2026.10.0rc1`.
Behavior baseline: `ce2838fe79cf1fda306ad853e8f102b91b2cc364`.
Implementation tested: `ceed94a52388ca95228881614ab367160c552a26`.

## Independent release checks

The acceptance harness invokes the actual build/verify command as a subprocess;
it does not import producer helpers or use the producer's test oracle. Expectations
were frozen separately before testing. An independent Git blob inventory and
ZIP reader check all 68 integration assets, including translations, service
schemas and image assets. Runtime bytes match the baseline exactly, with only
the authorized manifest version and fork ownership/support metadata changes.
The domain, name, dependencies, options, Python sources and identifiers remain
unchanged. HACS metadata exactly names the fork and verified root-layout ZIP.

AwesomeVersion identifies the candidate as CalVer. Both AwesomeVersion and
packaging order `2026.9.6 < 2026.10.0rc1 < 2026.10.0`. Two separate real builds
produce byte-identical ZIP and receipt files. Every installed payload member
matches the pinned Git blob. The receipt binds the complete file hash map,
source revision, version, planned tag and archive SHA-256.

| Real CLI cases | Expected result | Count |
| --- | --- | ---: |
| Two independent builds and positive verify | Exit 0 | 3 |
| Wrong revision, version or tag | Nonzero | 3 |
| Existing output directory | Nonzero | 1 |
| Dirty tracked or untracked integration input | Nonzero | 2 |
| Modified ZIP bytes; added, missing or replaced member; traversal or duplicate member | Nonzero | 6 |
| Mutated blob binding and removed artifact validation | Bad artifacts accepted by mutant, independently rejected with actual assertion exits | 2 |

Tampered ZIP cases recompute the sidecar archive and file hashes: a matching
sidecar cannot authorize changed runtime bytes or unsafe paths. The independent
oracle rejects traversal paths before consulting the expected member inventory.
Both source mutations are executed through the real CLI in disposable files.
The blob mutation builds a coherent receipt for altered `__init__.py` bytes;
the independent Git comparison fails. The validation mutation accepts a ZIP
with `../escape.py`; the independent path assertion fails. Neither mutation
changes the candidate source.

## Literal release-payload behavior

PASS: the actual generated ZIP was safely extracted into the integration directory
of a disposable clean clone pinned to the tested implementation commit. The
extracted package contained all 68 expected assets and matched the Git bytes
before testing. The unchanged historical independent behavior harness then ran:

| Independent behavior path | Passed |
| --- | ---: |
| Pure transport, isolation and provenance hand cases | 19 |
| DST, retry spacing and refresh integration hand cases | 8 |
| Actual Home Assistant service, coordinator and learning paths | 7 |
| Effective source mutations rejected by actual test assertions | 3 of 3 |

All 34 behavior tests passed, without skips. The historical harness and its
expectation files, contract and prior reports were copied byte-for-byte into an
isolated reference layout; original historical artifacts were preserved. The
harness only replaces controlled external weather/Recorder inputs and timing
boundaries. Actual integration service and coordinator methods execute. After
testing, a fresh hash readback covered all 68 package files, including non-Python
assets: every file still matched the built Git payload and the extracted clone
remained clean. Neither the source integration nor any running installation was
changed.

The first author full-suite run separately reported 138 passing tests and one
existing time-dependent rollover failure. The unchanged baseline and candidate
both reproduced that original test failure. This independent report makes no
claim that the full author suite or publication gate passed; the coordinator
records those separately.

## Artifact binding

- ZIP SHA-256: `4fe6e5be5826e938a36dde019f3d426434b3af559a2f6f33e55bad6b4dc795ba`.
- Receipt SHA-256: `ceddbedb22e80275e39b6381359f242ae1b49b4726acba3b0718612852e9fdf6`.
- Independent release harness SHA-256: `1af235e769c8c5a0615ab0f0dabeabbf54aad603d8a84296c67785e2ea789af2`.
- Independent expectations SHA-256: `68d86fea3cff41e14726391668b4bb6759a8ab29f185f009489e02226f6982b2`.
- Historical behavior result JSON SHA-256: `dbbeae49ca581e3466929669cd9d818c53da9058b2c1f57ba0be9f7e7b8dd3b8`.
- Historical behavior harness SHA-256: `3054d70a511935bb86f0083862c34162c669725669302c22a05a420ba5121be7`.

Reproduce the public release checks from a clean committed checkout:

```sh
python3 tests/acceptance/fork_release_r.py \
  --repo . --expected-rev <full-commit-sha> \
  --work <new-disposable-directory> \
  --version-python <python-with-awesomeversion-and-packaging>
```

The harness also installs the literal ZIP into a disposable pinned clone and
checks that all extracted bytes match Git and its worktree remains clean. Raw
JSON, mutated artifacts and logs belong in ignored generated outputs, outside
the public source documentation. This is local synthetic release/compatibility
evidence. It does not establish empirical winter quality, P10 calibration,
recovery safety or productive acceptance, and does not install or switch any
running integration.

# Fork candidate 2026.10.0rc1

Status: implemented candidate, pending independent acceptance and final external
review. No publication, HA installation, source switch or productive activation
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
`v2026.10.0rc1`; a GitHub prerelease must remain non-latest. Follow
[fork workflow](fork_workflow.md) for exact build/verify, future migration and
rollback procedures. The separate release receipt binds the final committed
revision and member/archive hashes; do not infer those from this document's commit.

## Implementation verification

Local implementation checks on Python 3.13.11: complete pure suite 267 passed
(including 20 release CLI cases); Ruff 0.15.20 lint and format passed (68 files);
mypy 1.19.1 passed (32 runtime source files); inherited HA module imports passed.
The complete inherited HA suite is still running at implementation freeze; its
result and the exact freeze pin are supplied separately to the coordinator. Independent R and final review evidence are
separate gates and must be attached before publication. CI workflows retain all
inherited jobs and read-only permissions while adding `fork/stable`, `release/**`
and manual invocation. Release helper lint/format is added to the existing job.

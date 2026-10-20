# Mandatory review implementation: internal pre-review (2026-10-20)

Frozen implementation base: `a8ba20b2257cc7a747542fc45c08528273f0f664`.
Classification: functional workflow helper plus policy/CI/documentation changes;
external full and additional meta review remain mandatory. This document records
local implementation evidence only, not independent acceptance or release approval.

Changes: new Helios AGENTS contract, complete-snapshot review CLI and convenience
facade, pinned Gemini provider wrapper, attributed HA-Config/ESS transport with
strict ACKs, optional local pre-push hook/installer, offline CLI tests, CI shell
syntax coverage, workflow/context/scope documents and conditional HACS runbook.
The existing CI pure suite includes the new tests; pinned Ruff covers scripts and
tests already. Runtime sources, HACS metadata, release assets and PR #7 head were
not modified. No provider call, push, hook installation or HA write was performed.

Internal inspection checked complete delivery scope, source/policy pins, model
selection, required context without truncation, verdict/findings/conditions,
transient-only bounded retry, ACK/final-turn handling, source/artifact/provider
identity drift, actual pushed SHA and explicit frozen-base selection. Strict
reports with any finding/condition require correction and a new review. Receipts
bind current trusted policy separately from an explicitly selected older target;
subsequent policy commits invalidate them, so freeze final HEAD before real calls.

Local validation: 13 real-CLI offline simulation tests passed (11.30s), including
tracked/untracked/source drift, report tampering, actual pushed SHA, full+meta
coverage and transport failures. A counter proves 503 retries once then succeeds;
permission+503, wrong ACK, malformed final and missing final each make one provider
attempt even with two configured retries. The full pure suite passed 280 tests
in 14.70s; its sole warning is the
intentional duplicate-ZIP negative fixture. Pinned Ruff 0.15.20 lint and format
passed across all 72 Python files. Shell syntax and `git diff --check` passed.

Coordinator separately rechecked immutable rc1 at a8: pure 267 passed in 3.51s,
Home Assistant 139 passed in 95.03s, Python 3.13.11. HA command:
`python -m pytest -o asyncio_mode=auto -n8 -q tests/ha` in the reserved HA environment.
These checks do not substitute for the independent policy R or real Gemini review.

Remaining limits: local hooks are optional and can be bypassed by a human; no
GitHub provider-backed enforcement or branch protection is claimed. Review output
and receipt hashes are local integrity/process evidence, not cryptographic
provider attestation. Unknown/binary or unsafe context fails rather than silently
truncating. Review, merge, publication and conditional HA migration are distinct
gates; the migration runbook is prospective. Independent R and coordinator
external review/CI readback remain open at this implementation commit.

Intended commit: `infra: require pinned Gemini review for every Helios delivery`.

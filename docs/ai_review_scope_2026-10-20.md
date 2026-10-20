# Mandatory review: scope and expectations (2026-10-20)

Frozen behavior base: `a8ba20b2257cc7a747542fc45c08528273f0f664`.
Implementation branch: `feature/mandatory-ai-review` in `/home/tg/Helios-Forecast`.

Add a Helios-specific mandatory Gemini review gate for every future delivery,
including documentation, policy, CI, scripts and runtime changes. Review the
entire delivery against an explicitly selected frozen base, never just its last
commit. Local interim commits may be marked implemented_pending_review. No push,
merge, release, tag replacement, HACS change or HA installation is part of this
implementation. Existing runtime sources and rc1 assets remain unchanged.

The user authorized sending Helios diffs and selected source/document context to
Gemini via Agy on 2026-10-20. This grants review transport only, no credentials,
secrets or deployment permission. Pin `Gemini 3.8 Flash (High)` using `agy --model`;
no provider/model fallback or global configuration mutation.

Review only clean committed snapshots. Reject tracked edits and all untracked
nonignored files before preparing context, rather than omit them. Include the
whole diff and complete changed text files; full review includes all runtime
Python/JSON sources. Missing, binary changed, unsafe or undecodable inputs fail
closed. Tool outputs live in ignored `reviews/ai/`, avoiding receipt recursion.

Reuse the HA-Config transport derived from ESS, with strict chunk ACK validation,
bounded transient-only retries and a separate final turn. Preserve raw prompt,
response, stderr, stream transcripts and command/exit evidence on failure too.
Require one strict final JSON verdict and structured findings. Conditions and
findings block delivery until fixed and reviewed again. Never infer approval from
an empty response, CLI exit alone or informal prose.

Receipt checks bind the frozen base, target commit/tree, reviewed content, mode,
model, prompt/report hashes and actual transport command/exit. Changes after
review invalidate it. A local optional pre-push hook checks each pushed revision;
GitHub CI exercises offline gate/transport tests, not provider-backed enforcement.

Validation: offline real-CLI tests for all-change context, clean snapshot rules,
receipt and source drift, malformed verdicts/findings, wrong/empty/missing ACKs,
missing final turn, permanent failures and bounded transient retries. Run the
complete pure suite and pinned Ruff lint/format. Perform internal diff review,
then independent acceptance and coordinator Gemini full (main base) plus meta
(frozen behavior base) review before delivery. HA tests remain coordinator-owned.

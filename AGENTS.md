# Helios-Forecast agent contract

Permanent work root: `/home/tg/Helios-Forecast`. Repository implementation and
`CONTRACT.md` outrank historical notes. Preserve upstream attribution and GPL-3.0.
Read `docs/fork_workflow.md` and affected contracts before changing behavior.

## Mandatory independent AI review

Every future change requires a completed Gemini review before delivery, push,
merge, release or installation, including docs, policy, CI and helper changes.
Local interim commits are allowed only as `implemented_pending_review`.
An unchanged commit or historical review does not cover a new delivery.

The user authorized Helios private diffs, selected code/docs and review metadata
via Agy/Gemini on 2026-10-20. Scope is review only; never include credentials,
secrets or site configuration. No deployment, publishing or HA permissions follow.
Use only `Gemini 3.8 Flash (High)` via explicit `agy --model`; no model/provider
fallback, global model configuration changes or unbounded retry.

1. Define the named scope, frozen complete delivery base and behavior expectations
   before implementation. Inspect status and preserve unrelated changes.
2. Run relevant local tests and inspect the full delivery diff: correctness,
   contracts, compatibility, data provenance, docs and permission boundaries.
3. Commit a clean snapshot, then run `bash scripts/ai_review.sh --full --ref BASE`.
   For scripts, hooks, CI, policy or permission changes also run `--meta` against
   the same complete delivery base. `--target PIN` explicitly reviews an existing
   committed target using current trusted review policy/helpers.
4. Resolve every finding/condition and review the corrected snapshot again.
   Use `python3 scripts/ai_review.py check --ref BASE --mode full --receipt PATH`
   (and meta where applicable) immediately before delivery. A successful CLI exit,
   prose approval or stale receipt never substitutes for a valid strict report.
5. Record files, tests, internal review, remaining risks, base/target pins and
   receipt paths in `docs/`. Provider artifacts stay ignored in `reviews/ai/`.

Raw prompts, responses, transcript and receipt bindings are retained on failure.
Missing/wrong ACKs, missing final turns, malformed JSON and empty responses fail
closed; never blindly retry those failures. Only bounded classified transient
provider errors may retry. Findings and conditions require fixes and a new review;
there is no automatic severity waiver or implicit acceptance.

The optional local hook (`bash scripts/install_review_hook.sh --ref BASE`) checks every
pushed SHA, including explicit refspecs; its local `aiReview.deliveryBase`
configuration pins the complete delivery base and must be selected explicitly; review artifacts must cover that target
and the entire pushed range. It rejects deletion and requires full plus meta for
governance changes. Install only after reviews are ready. GitHub CI runs offline
regression tests; this is not server-side enforcement of provider reviews. Do not
claim branch protection or provider-backed GitHub checks exist.

A review or merge never grants rollout permission. Preserve published rc1 tags,
assets, PR heads and runtime state unless the user explicitly authorizes that
specific action. No productive changes are implied by this policy.

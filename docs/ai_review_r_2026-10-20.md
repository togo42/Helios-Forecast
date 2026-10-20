# Independent mandatory-review acceptance (2026-10-20)

Result: local review-workflow acceptance passed: **39 real-CLI cases and two mutation controls**. This is offline transport simulation only. It grants no provider review receipt, forecasting acceptance, publication, merge or HA installation permission.

## Frozen expectations and scope

Expectations were declared before inspecting the implementation: complete frozen-base delivery coverage for new documentation, runtime and CI changes; clean committed snapshots; source/base/target/evidence drift rejection; pinned Gemini model; exact ordered chunk ACKs and a separate strict final verdict; blocking findings and conditions; actual pushed-SHA and new-branch scope; real failing mutation assertions; unchanged runtime/HACS/release tag. No producer test helpers or implementation modules are imported.

Workflow implementation pin: `36a2546a60414eaa8c0b2894c22e4d49a1c2460f`. Frozen behavior base: `a8ba20b2257cc7a747542fc45c08528273f0f664`. Independent harness: `tests/acceptance/ai_review_r.py`, SHA-256 `27c007a32e95f689fd4fb9c399ff6835c4e9c71f273181cb98ec31c773d89fa9`.

## Executed evidence

`python3 /tmp/ai_review_r_draft.py --source /home/tg/Helios-Forecast --expected-rev 36a2546a60414eaa8c0b2894c22e4d49a1c2460f --work /tmp/helios-r-final-pin --mutants`

The staged script was byte-identical to the versioned harness at the SHA-256 above. Replace its path with `tests/acceptance/ai_review_r.py` to reproduce.

The final positive fixture delivered three sequential context chunks and one separate final turn. The prompt contains complete new docs/runtime/CI contents, including the last document marker. A fake `agy` executable runs only inside throwaway fixture repositories. Actual argv pins `Gemini 3.8 Flash (High)`. Fixture receipts bind their provider and repository and are rejected from another repository. They are never production review evidence.

The 39 cases cover positive prepare/run/check, strict well-shaped blockers and conditions, malformed/empty/unknown/duplicate-key verdicts, permanent provider nonzero exit, wrong/suffixed/missing ACKs, missing final turn, malformed transport JSON, tracked/untracked drift, alternate base/target/HEAD/policy HEAD, receipt exit/command tampering, provider executable drift, artifact edits/deletions, missing selected hook base, exact pushed target, unrelated pushed target and new-branch scope. The author separately owns bounded-transient-retry counter tests; R does not claim independent retry evidence.

Mutation controls each execute the same independent assertions in a child process:

| Mutated guard | Observable incorrect behavior | Harness result |
| --- | --- | --- |
| Clean snapshot guard disabled | Dirty tracked document check returns 0 | Actual `AssertionError`, exit 1 |
| ACK comparisons disabled | Wrong ACK run returns 0 | Actual `AssertionError`, exit 1 |

Both unmodified positive controls pass before mutation. No mutation is written to the source repository.

An early pre-push finding was corrected before this acceptance: branch creation could previously select an empty or narrower scope. The gate now requires explicit `aiReview.deliveryBase`, matches receipt scope to it, rejects base=target, and requires full plus same-base meta review for policy/tooling changes. The independent new-branch and wrong-scope cases pass.

## Integrity bindings

These are actual SHA-256 values from the final fixture run; the prompt, report and snapshot below are synthetic simulation artifacts.

| Artifact | SHA-256 |
| --- | --- |
| `scripts/ai_review_transport.sh` | `36ecd41eddba40dc3d8ff3e338605b3d5d4afde77e993a682ae40de3c2570647` |
| `scripts/ai_review_provider.sh` | `da0b0db0a856d9525a653ecbc962aa17f180f2538a1314802d083fd138fe859d` |
| `scripts/ai_review.sh` | `79b8224db83e49cea26b65cad5de9c22515eb54351c273f33a72224c527b4dd1` |
| `scripts/ai_review.py` | `53b149eb4c86f253c5fa37989e5bd3fdf8971d6547f18cbe4b38856c67046061` |
| Simulation `prompt.md` | `d0975606ecb4a9e443c49aa15f123e722e70ab9d93ab5482e56e85b883ae787f` |
| Simulation `response.json` | `267a50d86e42d2f2771fe62994d148ee10e40d7ea50d62bef3a47ee2f5e35553` |
| Simulation `snapshot.json` | `cbc05294ecc9a1aa24ee3745c22157bae7e78df302bd15513311537e961ef29c` |
| Raw results JSON | `0e313fe5c38b5bc4ab6c09aad6ae09d45d6271bf4f96cc1766d5fe857021bc79` |

The harness independently verifies **71 protected files**: 68 runtime files, `hacs.json` and both historical release/clock acceptance harnesses, byte-identical to the frozen base. Immutable rc1 tag object remains `391e386a6a5d7144e585671f0e5f08552681a916`.

Pinned Ruff 0.15.20 check and format check passed for the R harness; Git whitespace check passed. Raw results, provider command/turn logs and mutation stderr are under `/tmp/helios-r-final-pin/`; these temporary artifacts are **not durable**. The reproducible harness and this report are versioned.

## Remaining gates and limits

Final coordinator provider-backed full/meta reviews must cover the complete delivery including these R files, after the final clean commit. Local hooks and unsigned local receipts are defense in depth; this work does not establish hostile-user tamper resistance or server-side provider enforcement. No real Gemini call, network operation, GitHub change, runtime edit, tag mutation or HA operation was performed by R. Forecasting runtime acceptance and release/installation authorization remain outside this R.

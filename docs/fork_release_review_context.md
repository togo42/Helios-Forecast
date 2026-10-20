# FORK-RELEASE-01: external review context

Review only this Helios-Forecast fork delivery. The invoked review helper is an
unchanged external transport; this repository has no ESS or Node-RED source tree.
Missing ESS documents and flow export checks are outside this delivery.

## Frozen scope and evidence

- Review the complete delivery diff against
  `ce2838fe79cf1fda306ad853e8f102b91b2cc364`, including documentation, the offline
  build/verify helper, its real CLI tests, independent acceptance and CI changes.
- Implementation freeze: `ceed94a52388ca95228881614ab367160c552a26`.
  Later documentation/test-evidence descendants must preserve runtime and builder
  blobs. The invocation's Git revision/status is authoritative for final scope.
- Read the complete expectations in `docs/fork_release_scope_2026-10-20.md`.
  Its bounded amendment permits only the inherited rollover test's clock fixture
  to become deterministic, with every assertion and production source preserved.
- All integration blobs must match the frozen base except manifest version,
  documentation, issue tracker and codeowners. Preserve domain, name, services,
  entities, configuration entries, storage, defaults and all forecast behavior.
- The ZIP installs its runtime files at archive root. Every member and the
  separate receipt must match pinned Git blobs; deterministic metadata, exact
  membership, safe paths, output collision and dirty-input rejection matter.
- HACS metadata belongs to the selected release. Main remains an unchanged
  upstream mirror, so it cannot carry the fork's release restrictions. A candidate
  requires explicit prerelease selection. HACS 2.0.5 source inspection and isolated
  extraction prove neither productive installation nor every discovery/UI path.
- Existing CI jobs and read-only permissions remain; fork/stable and release/**
  coverage is added. No automatic publisher or deployment workflow is introduced.
- Read implementation and independent evidence in the changed candidate/R
  documents. Inspect what the assertions actually prove; do not invent missing
  tests or reinterpret synthetic results as empirical forecast quality.
- No production HA installation, source switch, runtime mutation, upstream PR
  merge or ESS control activation is included. No winter, calibrated daily P10,
  DC-constraint or recovery acceptance is claimed.

## Review output

Respond in German. Report concrete findings with existing file/line or function,
effect and proposed fix; distinguish confirmed bugs from residual risks. Keep
positive narration to a minimum. Do not invent PR numbers, APIs, test results,
file names or source changes. No tools or commands: use supplied context only.

Give critical, medium and low findings; logging/dashboard and Node-RED impacts;
then mergeable / not mergeable / mergeable with conditions. These latter impacts
are normally none for this metadata/packaging-only delivery. Include a compact
finding table (or explicitly no findings) and exactly one fenced JSON block:

```json
{
  "findings": [],
  "active_findings_recommendations": []
}
```

Each nonempty finding needs `id` (GEM-001 etc.), `severity`
(`critical|medium|low`), `file`, `area`, `problem`, `suggestion`,
`status_suggestion` (`open|fixed|accepted-risk|obsolete|none`),
`node_red_flows_relevance`, `dashboard_relevance` (`yes|no|unknown`) and
`active_findings_action` (`none|add|update|close`). Do not treat successful CI,
review, Git tags or prereleases as productive or empirical acceptance.

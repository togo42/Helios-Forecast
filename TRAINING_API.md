# Conservative learning: expectations frozen before code

An explicit `strict_learning_quality` checkbox, off by default, is available in
installation settings next to the optional curtailment entity. Strict mode learns
only buckets wholly covered by the configured signal's explicit historical `off`
intervals. Any `on` overlap, unavailable/unknown state, missing initial state,
missing entity or failed history excludes the hour. A point observation alone
cannot establish an entire hour. Users must configure a signal covering their
installation's actual constraints; an off signal is no universal physics proof.
No inverter-specific threshold is added. Legacy SoC/cap detection and learning
remain unchanged when strict mode is off.

The same selected production bucket list feeds residual and analog learning.
Provenance reports strict, counts of clean/constrained/unknown input hours, and
constraint_quality known/partial/unknown, separately from forecast reliability.
Input hash and extent describe the actually selected bucket list. A wholly
unknown strict window yields physical forecasts without learned correction.

Checks: full-hour off, first sample mid-hour, unknown gaps, partial on, legacy
unchanged, missing/failed signal, both learning inputs identical, UI round trip,
and unknown buckets rejected in strict mode. No training quality certification.

Only new locale keys are translated; existing translations are preserved.

# Optional provenance: expectations frozen before implementation

`get_forecast` without `include_provenance` (or false) retains its exact response.
With true it adds `provenance`, schema `helios.forecast.v1`. The existing `watts`
is a corrected model point estimate, not a calibrated median. P10/P90 remain
marginal values; no daily quantile is introduced.

Original successful HTTP JSON receipt times and canonical payload hashes are
retained across cache copies and last-good fallback. Provider issue time remains
null because it is not supplied. Parsed complete weather input has a separate
hash, including ensemble spread. Completion is captured after the refresh has
computed its outputs. Configuration includes resolved location/layout/cap. Model
binding hashes the actually installed Python source files and manifest version;
it is not a feature-generation or training-process attestation. Learning hashes
actual bucket inputs, reports requested window and observed input extent separately,
and never invents a trained-until time. Unknown constraints remain unknown.

Checks: default service equality, opt-in null before successful update, HTTP receipt
preservation, stable canonical hashes, changed weather/config/buckets/source hash,
JSON-safe output, and completion not earlier than its inputs. No forecast schema,
Energy provider, archive ownership or production-control change.

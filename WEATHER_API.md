# Shared weather requests: expectations frozen before code

Same running event loop, session object, URL and parser share one request, including
its retries, and successful parsed values for at most 300 monotonic seconds.
Each consumer receives a deep copy. None, errors and cancellation are not cached.
Cancelling one waiter preserves another; cancelling the last waiter cancels and
awaits owned work. Completed cache entries are bounded to 32, independent of live
requests. No HTTP or forecast schema changes. A later provenance addition must
retain the original network receipt when a cached value is copied.

Checks: concurrent duplicates, parser/session/URL separation, copied mutable lists,
expiry boundary, failure then success, exceptions, one/all waiter cancellation.

## RC2 historical reuse

The optional `WeatherHistory` path is per config entry. Direct `fetch_weather`
callers retain their existing request behavior. The coordinator initially requests
60 past UTC days and eight forecast UTC days. Later refreshes request one past
UTC day and eight forecast days, replacing every returned row including `None`.
This repairs at least the existing six-hour archive overlap. Older rows are reused;
missing timestamps outside the recent window trigger a full bounded backfill, at
most once per 24 hours, including failed attempts. Missing individual variables do
not cause repeated historical downloads. Provider revisions older than the recent
window are not periodically refetched unless a historical hour is missing.

If the large backfill fails, a short request may supply a usable real forecast
with incomplete learning history. Its missing past is not filled. Backfill attempts
retain the existing bounded HTTP timeout/retry policy; no cold-start latency bound
or complete forecast availability during provider outages is promised. Cancellation
propagates and launches no short-request fallback. The latest failed/empty short
request leaves the existing coordinator last-good behavior intact for the same
weather identity; a changed identity cannot reuse the previous site's series.

History identity binds the four-decimal API coordinates, resolved base and spread
models, variables, and explicit parser/schema revision. Reuse keeps at most 60 full
UTC days plus the elapsed part of today (1,464 historical rows). Future rows are
returned from the fresh request only; old forecasts never become observations.
Every assembled row is bound to its original successful HTTP receipts; each receipt
adds `used_hours` specifying its contribution. `retrieval="assembled"` and the full
input content hash distinguish assembled history from one new network download.
`received_at` remains the fresh base response's original receipt instant; it does
not date every reused historical row.

The HA Store key `helios_forecast.<entry_id>.weather_history` persists only elapsed
rows, identity, original receipts and last backfill-attempt time. It contains no
site configuration or credentials. Restore checks schema, identity, checksum,
row/receipt/serialized-size bounds, finite-or-null values, UTC-hour alignment and
future dates. Invalid data causes fresh backfill; persistence errors do not discard
usable fresh weather. Restored history alone never passes a cold-start update:
a real fresh request must succeed. This cache is neither a backup nor an immutable
forecast archive, and source uninstall/rollback must preserve existing HA state.
Reloading or unloading an entry preserves this cache. Explicit deletion of the
config entry removes its weather-history Store along with trend and day-ahead
state through the existing integration cleanup lifecycle.

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

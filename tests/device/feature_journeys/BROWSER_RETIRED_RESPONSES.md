# Closed browser authority and original response inventory

`GET /runs/<run>/browser-retired` is an explicit authenticated read after the
actual World/Tablet run closes. The ordinary `/browser`, resources and controls
remain unavailable. The new getter returns `browserFixtureVersion: 2`; the active
getter remains literal version1. Existing response instance, IDs, status, byte
counts, digests and response timestamps remain unchanged. This is a server
history read, not a native document, rendering, callback or quiet observation.

The bounded archive retains at most64 runs. Evicted/unknown originals stay
unavailable. It never reopens resource authority. A new close cannot overwrite
an existing retired identity. Outward results are copies. A separate
`browserRetirementVersion: 1` holds the actual close observation and up to256
late requests for known controlled resource paths. Overflow or unavailable/
regressed provider clocks make the source incomplete, not an empty success.

The HTTP handler observes requests before the existing retired-resource checks,
including the foreign resource-only listener. Status is read from actual
serialized response headers, not the requested `send()` argument. The hash and
size identify that actual serialized response body. A write receipt is retained
only after the real `wfile.write()` return. Actual handler finally entry has its
own field; it is never labeled callback return or native drainage. Missing write/
finally evidence remains explicit. Denials are not served resource responses;
they never add a successful response ID to the original inventory. These fields
cannot replace independent native pending/callback/lifetime/quiet evidence.

The pure reader accepts both literal active v1 and the explicit retired v2.
Retired response history cannot grow or return to active format after retirement;
only actual late-attempt metadata may append or fill originally pending fields.
No original response clock is retimed. Tokens for a retired request also retain
its actual inventory instance, preventing callback attribution after eviction.

The World Source5 final fence selects the new getter only for its explicitly
inactive capture. Its exact run and retired format are checked before another
native clock query. Ordinary active capture and older historical Source3/4
representations keep their existing routes and semantics. This integration is a
separate Whole packet; the neutral HTTP/archive reader requires no Whole owner.

Focused tests use actual authenticated localhost HTTP, resource bytes and kernel
files. Native/Qt/clock producers in the Source5 join tests are explicit models.
Prospective verification executed the proposed Python in an isolated process
while shared files were frozen. After the shared patch was applied, all nine
authenticated HTTP cases passed (0.158 seconds), including an actual request
held between headers and write/finally, late POST denial, bounded eviction and
unavailable clocks. All twelve original active-browser cases also passed
(0.270 seconds). Two actual Source5 joins passed separately (0.896 seconds). Native
compilation, devices, the full World journey and real CPU freshness remain
unqualified by these narrow tests.

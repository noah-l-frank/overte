# Original iOS Web callback ownership

`ios/web/IOSWebClosureTrace.h` supplies a passive version-1 callback ledger for
actual owned HTTP fixture contexts. It requires `OVERTE_E2E_FEATURE_TESTS` and
the existing dedicated test-script/results launch arguments. Outside that
boundary it creates no leases or native completion handlers.

Each context retains its original native handle, creation, policy grant,
document epoch, surface, source-identity SHA-256 and fully encoded policy source
URL. The URL must be an actual run/ticket `index.html`, `reference.html` or
`graphics-marker.v1.html` fixture source. Contexts created before native view or
document creation can contain zero creation/page counters; these describe the
actual earlier callback owner, not a later invented document. Inline, arbitrary
Web content and other resources are outside this version's coverage.

The original JavaScript, WK snapshot, native presentation, content-rule-list,
notification, Qt script-reply and download completion closures hold shared
leases. A lease retires only when the last actual callback copy is destroyed.
A weak owner returning early, QObject destruction, timer cancellation or live
registry removal cannot retire it. The actual Qt callbacks carry the leases;
parallel no-op observer connections are not used. The test-only fire-and-forget
JavaScript path adds a completion with no product side effects to retain its
actual callback lifetime, without executing JavaScript twice.

Metadata remains bounded to 1024 contexts and 262144 output bytes. Overflow,
counter exhaustion or original clock regression fail closed. Tombstones and
cumulative created/retired counters never reset or disappear. The ledger does
not retain views, native blocks or image resources itself.

The existing Test interface reads the provider registered by the actual iOS Web
module. This avoids interpreting a separate module's singleton as an empty
inventory. The probe writes only the original response, through the existing
atomic private diagnostic path. Missing providers produce incomplete evidence.
The closed `feature-ios-web-closures` command accepts only schema, original
nonce, run and fixture root, with no script, expected value or reset parameter.

`ios/adapters/web_closures.py` validates original bytes, exact source/process/run
ownership, immutable context prefixes, cumulative counters and fresh source
cursors. The existing HTTP/AFC component factory joins each read to three
independent original native clocks; no AFC timestamp or host UTC becomes native
freshness. Acquisition and final validation share a 1500 ms ceiling. An
uncertain request is never resent. `drained()` requires previously admitted,
nonempty original callback history and fresh retained contexts with zero
pending callbacks, including newly added contexts. It does not implement a
quiet window or replace its caller's durable ownership.

Validation: 27 selected no-build cases pass across the new closure parser,
actual HTTP/AFC factory, Node probe and existing shared/iOS Web DOM regressions.
Counterexamples include held callback copies, lost delivery, disappearing
contexts, foreign runs/PIDs, source replacement, counter regression, duplicate
JSON, stale/future evidence, incomplete inventories, slow final guards and
unknown callback kinds. Native hook tests inspect source only. Native callbacks
and the OS boundary remain synthetic; native compilation and devices are
unverified.

This facet is not a complete Web or Graphics adapter. WK view deallocation,
native bitmap copies, QQuick software buffers, renderer texture uploads,
recycler/GPU allocation retirement, active policy grants and final quiet-window
composition still require separate original lifetime sources. No full feature
capability is advertised.

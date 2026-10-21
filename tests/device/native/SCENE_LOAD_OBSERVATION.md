# Original iOS serverless scene request and callback lifetime

`native-scene-loads` version 1 observes the existing iOS application load path.
It does not navigate, cancel, retry, change a product guard or establish rendered
success. The ledger/parser decomposition derives from frozen Phone commit
`fe4684bf46585088370b3a328a738f147e670b97`; Android ticket/dispatch semantics
are not imported. Native additions remain uncompiled and devices untested.

In an E2E build, iOS records actual local-file reads and ResourceRequest
generations, results, byte counts and phases. The ordinary existing generation
guard remains authoritative. Actual owner-thread deliveries and the existing
iOS queued viewpoint closure each retain a separate lifetime lease. Qt closure
destruction and ResourceRequest connection destruction release their original
leases; an input/commit ACK cannot clear them. A newer committed request cannot
hide an older pending request or delivery. The 128-row immutable ledger fails
closed on exhaustion and has no reset operation.

Instrumentation is gated by `OVERTE_E2E_FEATURE_TESTS`, `Q_OS_IOS` and the
existing `--testScript` flag. Ordinary applications retain their existing load
path. Native E2E dispatch substitutes only an equivalent context-bound Qt
queued closure where the original cross-thread invocation was already queued,
so its actual retained lifetime can be observed. No functional fix or Phone
navigation ticket is added. The scheduled iOS viewpoint still uses its original
generation/scene guard and original ordinary AddressManager call.

The closed command has version 1, `commandId: ios-<32hex>`, action
`feature-scene-load-observe` and `runId: <32hex>`. It accepts no URL, expected
generation, geometry, result or cleanup claim. `featureSceneLoadObservation`
reads the original process ledger on the application thread. The existing
probe writes the untouched source to `feature-scene-load.json`, atomically
through the native private result-file path. HTTP/AFC transport, PID/birth,
source cursor, native clock and original immutable request prefixes are checked
by the shared reader and iOS factory.

The record contains original request/delivery IDs, actual resource URL hashes,
generations, start/update/release clocks, phases, pending flags and original
result/byte counts. Resource identity excludes only the viewpoint location
query. `committed()` requires one actual current committed request, complete
history and zero pending leases across the entire ledger. It is a lifetime
prerequisite. Original scene/avatar/camera, provider and image measurements
must independently prove the product outcome.

Sixteen parser/probe/fixture host cases cover real original-prefix admission,
pending old groups, closure lifetime, stale/foreign clocks, changed histories,
partial writes, missing hooks, closed iOS command grammar and no resend.
Packets/native lifetime transitions are synthetic; Node runs the existing probe
implementation. No native compilation, application or device is executed.

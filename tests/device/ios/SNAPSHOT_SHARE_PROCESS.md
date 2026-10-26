# Closed Snapshot Share extension process originals

The repository Appium process plugin adds two narrowly closed passive commands:
`mobile: overteSnapshotShareExtensionInfo` and
`mobile: overteRetiredSnapshotShareExtensionInfo`. Each accepts only the
configured archive bundle and a fresh nonce. The original scope still requires
the actual physical driver, exact archive `opts.bundleId`, unchanged device and
session, and the pinned eligible SDK. The only additional process is that
archive's fixed `.receiver` bundle. Callers cannot select another extension,
provide a PID, request an absent result or change the driver bundle. Existing
generic process commands continue rejecting every foreign bundle.

`SnapshotShareArchiveContext` requires the actual historical Share archive
code-admission owner. Its selected/installed complete forest must contain the
independently parsed embedded extension whose real bundle identifier equals
this exact derived receiver. The context retains the selected IPA identity,
original archive process and original process-source lifetime. During the
external Share UI it uses only explicit OS-only background continuity;
foreground native/UI guards remain unchanged.

A live extension observation reads two actual DVT bundle PIDs, two numeric
`isRunningPid` results and original XCUITest application states. The first
consistent nonzero PID creates one immutable source anchor. Later live reads
must observe that same PID; a new live process cannot replace the original
anchor. Empty initial reads have no anchor and cannot authorize retirement.
The actual Receiver original ledger must independently name the same qualified
bundle and the same anchored PID.

Retired observations preserve the original anchor and separately query the
current receiver bundle and the original numeric PID twice. A different current
PID, an old PID that still runs, missing API support, a running application
state or any partial/contradictory observation cannot establish absence. The
source returns these actual partial observations as presence diagnostics;
the strict host absence reader requires both bundle PIDs to be zero, both old
PID checks to be false and both application states to be nonrunning.

The original DVT service and actual Node socket remain owned until both SDK
closure and the original socket close callback have drained. A close ACK is
insufficient. Unknown, malformed, timed-out or failed reads poison the source;
late acquisition still closes only its original service and never emits a
late successful receipt. Pending resources remain visible to session cleanup.
Every source clock retains its original Node host UTC/monotonic values. The
extension's native monotonic epoch is kept separately and never transplanted
into the process reader.

The version-1 `snapshot-share-extension-process` DTO retains the original
anchor, fresh query originals, source birth/sequence and actual connection
closure. The version-1 `snapshot-share-extension-absence` summary explicitly
requires a later quiet window and complete feature qualification. No immutable
host query journal, repeated quiet interval, UI handoff or filesystem retirement
is inferred from this component alone.

The [durable query owner](SNAPSHOT_SHARE_QUERIES.md) now retains exact source
JSON by original nonce, binds actual Receiver metadata and validates separate
real Node/owner quiet intervals. This does not complete the outer normal Share
input/import/retirement journey or activate the repository plugin.

On 2026-10-26, the explicit host selection passed 37 tests in 7.935 seconds:
eight new Share process tests, nine existing process-plugin tests, ten existing
retired-process tests, three Photos factory/context tests and seven Share code
admission tests. The actual checked-in Node plugin executes against declared
fake DVT/OS producers and actual unconnected Node sockets. Its original JSON
also passes the actual Python reader and independently admitted archive
context. Cases cover foreign archive/extension selectors, requested success/PID
fields, immutable continuation anchors, wrong Receiver PID, partial absence,
missing/boolean APIs, lost/late connections and close callbacks, late native
acquisition and retained cleanup responsibility.

These are repository source and host-only checks. No installed plugin was
changed, no Appium server/service was started, and no device, native build or
laboratory was used. Actual SDK support for observing this extension and the
native/device result remain unknown until separately qualified. Complete
Snapshot capability remains closed.

## Resume checkpoint after the requested pause

The user requested pausing after this packet to reboot. No further integration
starts in this session. The work belongs only to
`overte-ios-feature-adapters-resume-20261026`, branch
`test/ios/feature-adapters-resume-20261026`. Completed earlier packets are
`9dd266957b` (Photos Save/original/delete/retirement), `e16cf7c059` (independent
Share archive/embedded extension code) and `02bb9703af` (initial source/import
anchors and bounded original chunks). This process packet adds no completed
whole feature to the existing fourteen-feature count.

Resume with durable ownership of extension queries and original reply files,
binding the unchanged live PID anchor to the exact Receiver ledger, and fresh
separate Node-host and owner-host quiet intervals. Then connect the actual
normal Share open/cancel/receiver selection/receive/inspect/finish/import flow
to the retained client export operation, original capture PNG, independent
archive metadata/chunks, extension absence and conditional owned App
Group/Documents retirement. No current ACK or context helper supplies that
complete flow.

The outer Feature 11/14 Snapshot journey still needs pending-capture
cancellation, actual OS permission denial/recovery and system presentation
recipes, authenticated upload/body originals, independent Actor/scene image
witness, lifecycle resume, final client capture cleanup/restoration and paired
quiet/process retirement. Preserve exact legacy readers and existing capability
closure until the unchanged full journey and cleanup qualify. Builds, device
runs, services, installations, dependency changes and remote writes remain
outside this resumed source-only task's current authorization.

# Retained host responsibility for an ordinary HID contact

`TouchLease` is a source-only host transport primitive. It neither exposes a
canonical RPC nor enables a Lifecycle capability. It reports no native held,
released, weak-death or SDK resource-absence fact. Native/device execution and
installed laboratory SDK compatibility remain unverified.

The primitive reuses the existing touch coordinate codec and authenticated
`touch_session` context. The caller supplies actual binding/run and a mandatory
fresh candidate/session/PID/foreground check. Checks run before and after
acquisition, before the durable Down intent and immediately before dispatch.
One retained asyncio worker owns the exact original factory, context, HID
object and normalized point through a normal contact report, ordinary release
report and original context exit. It creates no QML/drive-key setter.

The private `iosTouchLeaseVersion` 1 journal is durable before Down. A lost Down
is never resent; an old open journal cannot recreate an absent live worker or
acquire another HID object. Caller cancellation does not cancel the original
worker. Lost Up, context-exit or journal results remain owned. Up is attempted
once on the same actual original HID object, including after a lost Down
return. Swapping diagnostic aliases must never redirect cleanup to a foreign
context or file descriptor.

The original host request deadline is at most twelve seconds. Its watchdog
requests release; it does not assert a hard physical release deadline when the
original HID send is stuck. That unresolved task/context remains owned. The
`contextExitReturned` field means exactly that the original context manager
returned. It is not an independent proof that native contacts, all SDK
callbacks, sockets, media workers or process resources are absent.

The eighteen initial host cases pass with real private CAS files and actual
unconnected socket-pair descriptors, plus explicit HID/RSD/context models. They
cover unknown/failed sends and drainage, cancellation, original-object identity,
four continuity boundaries, changed binding/run, old journals, late acquisition
and typed deadlines. No device, RSD/HID connection, Appium server or runtime
service is started. A later immutable-intent follow-up is recorded separately.

Still wire a persistent canonical worker/RPC with actual process/service
ownership, original geometry admission and the [native touch/world
observations](LIFECYCLE_TOUCH.md). Only those fresh originals can prove current
held forward input, displacement and terminal contact release. Complete
Lifecycle also needs host/native quiet, Actor/image evidence, restoration and
paired ownership retirement. Keep canonical lease journals in the existing
`ios-lifecycle-` namespace so unresolved responsibility blocks ordinary teardown.
The default complete W3C/touch validators and existing HID session are unchanged.

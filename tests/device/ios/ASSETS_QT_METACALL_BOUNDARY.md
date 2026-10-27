# Optional QtCore MetaCall source boundary

This optional source patch prepares precise provenance for the existing
ImageReader indexed `setImage` invocation. It remains unapplied to an SDK,
uncompiled, and unexecuted as native code. The current ImageReader Source1,
ModelOrigin History5, TextureRelease1, and their completion flags are unchanged.
Queued attribution remains unavailable in the current adapter. Overall source
completion remains 5/14.

The [patch](../../../ios/patches/qtbase-overte-e2e-metacall-receipts.patch)
uses only the exact reviewed Qt 6.11.1 sources:

| Original function | Observation boundary |
| --- | --- |
| `QMetaMethod::invokeImpl` | Claim the actual indexed invocation at entry, then adopt its actual newly created `QQueuedMetaCallEvent` after original argument copying. |
| `QMetaCallEvent::placeMetaCall` | Observe actual dispatch entry, normal return or unwind around the unchanged slot/static-call/metacall branches. |
| `QQueuedMetaCallEvent::~QQueuedMetaCallEvent` | Observe argument-value destruction only after the original metatype destruct/destroy loop and conditional argument-buffer free return. |

The exact sources are the official Qt mirror's
[qmetaobject.cpp](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/src/corelib/kernel/qmetaobject.cpp),
[qobject.cpp](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/src/corelib/kernel/qobject.cpp),
and [qobject_p.h](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/src/corelib/kernel/qobject_p.h).
The [manifest](qt-metacall-source-patch.json) pins every original SHA-256, the
exact Qt version, and private API version1.

A future dedicated iOS E2E bridge must additionally require actual runtime
`--testScript` admission, exact runtime Qt version, and the exported API version.
The optional Qt API defaults to disabled. A missing/unavailable API cannot
upgrade current queued observations. That application bridge and a new strict
wire/host-reader contract are separate work; this packet adds neither.

The patch changes a private event layout. Rebuild the complete matching SDK and
all consumers of its private headers together. Application code must use the
exported QObjectPrivate API; never read extended event fields inline or replace
only QtCore in an existing SDK. This repository artifact does not install,
modify, compile, or build an SDK.

The actual native Dispatch supplies its generated opaque invocation identity,
actual target and actual method index within a synchronous binding scope. The
actual Qt invocation independently claims that scope before any product
metatype registration or copy can reenter. Its local token must reach the
actual event-creation site. An unscoped inner invocation cannot steal the outer
association, including when the outer argument constructor later throws. A
legitimate inner native Dispatch requires its own new scope and identity.

Each adopted event stores its own monotone event ID. No FIFO, equal payload,
URL, hash, raw-pointer registry key, script-supplied expected result, or lone
pending row proves that relationship. Actual receiver pointers are confined to
synchronous callbacks and must never be exported as addresses or retained as
ownership. The future bridge must validate actual weak Resource association,
invocation uniqueness, receiver and method, preserve append-only original
phases, and refuse weak resurrection. It must not hold its registry lock across
the product invocation. Unobserved nested MetaCalls mask outer identities.

The callback reads no argument values, payload bytes, URL/userinfo/query text,
content hash, GPU object or response origin. It records actual UTC milliseconds
and steady-clock nanoseconds in their own clock domain. The future observer
must remain bounded and passive: no product calls, event pumping, queries,
input, or payload inspection. The Qt side uses fixed TLS storage and lock-free
atomics: nesting16, event identities256, binding tokens1048576. It has no dynamic
result registry and retains no strong product owner. Callback false/throw,
callback reentrancy, observer replacement, disable after enable, invalid scope
nesting, and overflow latch a process-long independent failure without reset.
An earlier good receipt cannot survive that failure as current authority.

Normal slot return does not destroy queued arguments. Cancelled events can
destroy arguments without delivery. The final destructor phase establishes
only that the original argument-value destructors and conditional external
argument-buffer free returned. Inline backing storage, event/base allocation,
independent QByteArray copies, functor captures, KTX paths, QRunnable/thread
pools, decoder state, GPU work and full Resource retirement remain unknown.
Actor/backend/source/process/SDK end responsibilities remain open.

Host validation applies and reverses the patch only on fresh owned private
copies of the three exact originals. Unknown source and outside-scratch targets
refuse before result creation or git invocation. Separate declared Python
boundary models exercise reversed equal payloads with distinct event IDs,
foreign receiver/method, nested masking, cancellation, return before real Python
argument release, weak receiver expiry, product unwind, sticky observer failure,
capacity/reentrancy, and reentrant product argument-copy failure. Those models
do not execute Qt or prove its C++ implementation.

Use the explicit retained source root; the verifier has no download/build
fallback:

```sh
OVERTE_QT_CORE_SOURCE_REFERENCE_ROOT=/path/to/reviewed/qt-source-root \
  PYTHONPATH=tests/device:tests/device/ios/self_tests \
  python3 -m unittest -v test_ios_qt_metacall_source_patch test_ios_qt_metacall_boundary
```

Actual source patch/reverse checks and declared model checks cannot establish
native compilation, runtime API behavior, queued provenance, native argument
destruction, storage retirement, or device qualification. Their report keeps
every such flag false. No earlier 225.251-second TextureRelease1 result
qualifies this new source instrumentation.

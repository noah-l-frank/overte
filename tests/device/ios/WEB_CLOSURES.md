# Original iOS Web callback ownership

`ios/web/IOSWebClosureTrace.h` supplies a passive version-3 callback/native/software-resource ledger for
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

Validation: 38 selected no-build cases pass across the new closure parser,
actual HTTP/AFC factory, Node probe and existing shared/iOS Web DOM regressions.
Counterexamples include held callback copies, lost delivery, disappearing
contexts, foreign runs/PIDs, source replacement, counter regression, duplicate
JSON, stale/future evidence, incomplete inventories, slow final guards and
unknown callback kinds. Native hook tests inspect source only. Native callbacks
and the OS boundary remain synthetic; native compilation and devices are
unverified.

This facet is not a complete Web or Graphics adapter. CPU texture, Vulkan wrapper/allocation, original submission and recycler
retirement and final quiet-window composition still require separate original
lifetime sources. No full feature
capability is advertised.

## Version 2: native view, grant and bitmap resources

Version 2 adds native resources; Python reads versions 1, 2 and 3 without
inventing resource counts for legacy packets. Same-process source version
changes fail continuity. `resources` records cumulative `policy-grant`,
`native-view` and `native-bitmap` ownership separately from callbacks.

An Objective-C associated token belongs to the actual WKWebView allocation and
retires its lease when that native object destroys its associated token. The
token contains no strong WK view reference; Qt object destruction, removing a
view from its superview or setting the owner's view pointer to nil cannot
retire another native holder's lease. Native policy leases follow actual
successful grant creation and synchronous policy close. No policy calls or
native teardown behavior are added.

A test-only read-only QImage carrier retains the original WK snapshot allocation
and a lease through its implicit copies, including the view's image and
`frameSource` copies. Its actual external-data cleanup releases the retained
original image reference before the lease. Pixels, stride, dimensions and format
remain original. Failed carrier construction fails the source closed and
handles both Qt cleanup outcomes without duplicate deletion. Independent deep
copies, painting, conversion and GPU upload require their own lifetime source;
the native bitmap carrier does not claim to cover those allocations.

`drained_native_resources()` requires original admission of all three resource
kinds, retained callbacks and zero pending original native resources. The
callback-only predicate remains explicitly narrower. The canonical Graphics
runtime exposes the same existing HTTP/AFC source factory without advertising a
whole-area capability. Thirty-three selected no-build Web/closure cases pass,
including each held resource, new retained contexts, missing resource sources,
legacy packets and counter regressions. Native resource hooks remain uncompiled
and are checked only by source inspection and synthetic source counterexamples.
The additional software source is described below; renderer/GPU resource and
final quiet composition remain unfinished.

## Version 3: actual Qt software image provenance

`shared/IOSFeatureImageTrace` owns one shared-library registry. It traces actual
QImage implicit-copy identities and opaque source factories from the iOS Web
module. It retains no QObject, paint node or GPU object in the registry. Original
carrier cleanup removes only that carrier's registered identity and releases the
actual original image reference before resource leases. A failed registration
cannot erase another carrier's identity. Metadata is bounded to 4096 active
carriers and 1024 original scopes; overflow invalidates the original native
source instead of silently dropping ownership.

The original Qt software render path brackets both synchronization and rendering.
Actual owned `IOSWebView::paint` calls record their original image context inside
that frame. Missing paint framing fails the source closed. The finished original
software image carries the union of inherited and newly painted sources through
`SharedObject` delivery, fetch/swap, copies and retained offscreen images. Dirty
region rendering never becomes a full-clear receipt: old source ownership can
remain conservative until the actual allocation's last implicit copy dies.
No product pixels are cleared or restored by this instrumentation.

The actual QQuickPaintedItem base `updatePaintNode` still creates and updates its
native node. Resource-only child tokens attach pending original paint leases to
that node and die under its real ownership. They contain no rendering commands.
Pending source metadata is consumed only after transfer to the actual node;
destruction with an untransferred actual paint invalidates the native source.
The QML object's removal is not a substitute for node destruction.

The Web entity's actual fetched software image supplies the provenance for its
post-conversion/post-diagnostic upload carrier. Dimensions, format, stride and
pixels stay original; the subsequent CPU texture remains a distinct source.
`drained_software_resources()` requires original admission of real node,
offscreen-image and upload-image ownership, plus native/callback drainage.
Native-only legacy packets cannot qualify these resources. New implicit copies,
retained nodes, missing paths or incomplete trace cannot become absence.

Thirty-eight selected no-build cases pass, including each independent software
resource, absent legacy source, changed original counts and new retained copies.
The native checks inspect source placement and closed ownership only. Qt image,
scene-graph and OS behavior remain synthetic/uncompiled; no claim of native
execution, pixel identity on a device or GPU retirement follows from these tests.

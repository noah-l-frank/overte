# Original iOS Web callback ownership

`ios/web/IOSWebClosureTrace.h` supplies a passive version-5 callback/native/software/GPU resource ledger for
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

Validation: 49 selected no-build cases pass across the new closure parser,
actual HTTP/AFC factory, Node probe and existing shared/iOS Web DOM regressions.
Counterexamples include held callback copies, lost delivery, disappearing
contexts, foreign runs/PIDs, source replacement, counter regression, duplicate
JSON, stale/future evidence, incomplete inventories, slow final guards and
unknown callback kinds. Native hook tests inspect source only. Native callbacks
and the OS boundary remain synthetic; native compilation and devices are
unverified.

This facet is not a complete Web or Graphics adapter. Whole-run durable admission, role-specific cleanup, original-world pixel
absence, complete quiet windows and final metadata retirement remain to be
composed with these sources. No full feature
capability is advertised.

## Version 2: native view, grant and bitmap resources

Version 2 adds native resources; Python reads versions 1 through 5 without
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
The additional software source is described below; GPU source is described below; final whole-run quiet composition remains
unfinished.

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

## Version 4: actual CPU/Vulkan resource and submission ownership

Actual software upload pixels supply immutable scopes to the resulting CPU
texture after `assignStoredMip`. Test-only members retire after original stored
pixels and backend object ownership. Vulkan texture construction reads those
actual scopes; another texture usage fails source completeness. Original strict
image/VMA allocation, staging buffer/memory, sampler and image-view creation
registers leases only after successful native calls and actual non-null handles.
No original native resource handles are exported in diagnostics.

`vk/FeatureResourceHandles` uses the existing recycler mutex and bounded maps.
It holds only metadata and leases, without retaining Vulkan objects or changing
native queue behavior. Wrapper or CPU texture destruction does not retire
queued images/views/samplers. The existing recycler's actual `vkDestroy*` calls
precede their ownership retirement. Actual VMA free and staging buffer/memory
destroy/free have separate original retirement hooks. Duplicate live handles,
overflow and map destruction with unresolved ownership invalidate the source.
No metadata reset can turn unresolved resource lifetime into absence.

Actual valid texture descriptors add their original scopes to a per-command
frame submission ticket. The actual `vkQueueSubmit` result records submission;
it cannot mark completion. The ticket joins the window's already existing
matching fence callback, composed with completed-frame capture callbacks. Only
that callback's actual success can qualify completion. No extra GPU wait,
submission, copy, fence reset or product lifetime repair is introduced.
Failed, unknown, repeated or missing completion leaves source completeness
invalid. Leases remain through actual FrameData and callback ticket copies,
including after a successful fence; destruction of an unknown ticket cannot
restore completeness. A replay without newly executed commands does not reuse a
previous ticket as a new submission.

Version-4 `drained_gpu_resources()` requires admitted originals for all nine
CPU/Vulkan resource kinds, retained native/software/callback history and zero
pending resource leases, including later-created contexts. Older packets stay
readable for their narrower source coverage and cannot qualify GPU cleanup.
The predicate still needs fresh acquisition, the full caller-owned quiet
window, independent original-world pixels and separate process-death evidence
when a restart retires an old source. It is not a whole-area capability.

Forty-five selected no-build Web cases pass. New counterexamples retain every
GPU resource separately, release CPU/native objects while recycler/fence work
remains, remove original upload sources, regress counters or report zero counts
with an incomplete source. Native source inspections verify successful-call,
actual destroy/free and original fence callback placement. Five existing static
iOS rendering inventory/contract checks also pass. These are source checks and
synthetic native counterexamples. No native compilation, Vulkan execution,
physical GPU lifetime acceptance, build or device test has occurred.

The complete reviewed no-build iOS selection passes 665 cases with zero
failures, errors, skips or blocked subprocess attempts. Twenty native compiler
cases are deliberately excluded by the private verification selector. Printed
negative-fixture messages are expected counterexamples, not suite failures.
This includes unchanged full Scripts and Authentication regressions and the
existing Graphics component/recovery selections. Native execution remains
unverified.

The reviewed common quick selection also passes 1172 no-build cases with zero
failures, errors, skips or blocked subprocess attempts; three native compiler
cases remain deliberately excluded. The five selected project documentation,
contract, input-selection, policy and coverage suites pass. Registry and
whitespace checks pass. The existing unrelated scissor-state static check's
obsolete-field baseline failure is not changed or weakened by this packet.

## Version 5: independently retained native holders

The same actual-object association now covers native WK delegates, UIKit
presentation/content controllers and returned WK snapshot UIImage objects.
Delegates acquire their original token before native view allocation, so a
failed allocation cannot hide a previously created native holder. Snapshot
objects acquire a token before weak-owner early returns. Removing a view,
releasing a Qt object or observing completed callback code is insufficient while
these independently held native objects remain alive.

One associated metadata bag retains every original context/kind on an actual
object, rather than replacing an earlier scope when a framework reuses an
object. A repeated acquisition of the same original scope does not double count
that holder. The bag has no strong reference to its native object, accepts only
its four closed native object kinds and is bounded. It adds no completion,
presentation, dismissal, navigation, timer or resource destruction operation.
Only actual native object destruction releases its tokens.

`drained_owned_resources()` requires version 5 and original observed delegate
and snapshot ownership in addition to the complete GPU/native/software path.
The Graphics marker need not open a native presentation, but any presentation
that actually exists must independently drain. Version-4 packets cannot qualify
these new holder lifetimes. These are the actual traced app objects; private
WebKit/CGImage/driver caches outside their ownership are not an asserted
framework-wide memory inventory.

Forty-nine selected no-build Web/closure cases pass, including each retained
native holder, an unopened presentation, missing original object sources and
legacy refusal. Native hook assertions verify attachment before owner guards
and native view allocation, and preservation of original scopes on reused
objects. Compilation and devices remain unverified. The earlier 665-iOS and
1172-common full selections apply to version 4; this additional version-5 packet
has the targeted selection and project/registry checks recorded with it.

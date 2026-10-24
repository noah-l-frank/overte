# Proposed same-authority World ray and input source

This is a source-only design for Root review, based on fixed native source
`032419eecc5737983f7a41d1bd677b948dc2c68e`. No protocol, producer, normal
input body, registry, public capability or Common16 predicate is changed by
this document. The following separate protocol name/version is proposed,
not registered. Phone's Common17/18 remain unrelated existing versions.

## Actual selected backend and consumers

The selected World chain is
[Web3DSurface.qml](../../../../interface/resources/qml/+android_interface/Web3DSurface.qml)
(line 91),
[Web3DSurfaceAndroid.qml](../../../../interface/resources/qml/+android_interface/Web3DSurfaceAndroid.qml)
(line 6), shared
[EmbeddedWebView.qml](../../../../interface/resources/qml/controls/EmbeddedWebView.qml)
`_load`, and Android
[EmbeddedWebBackend.qml](../../../../interface/resources/qml/controls/+android/EmbeddedWebBackend.qml)
`NativeWebView` with WorldEntity/Texture presentation. It selects the complete
original shared NativeWebViewItem, not the older PicoWebViewItem backend.

The existing ordinary ray route uses
[controller_protocol.py](../../openxr_input/controller_protocol.py)
`input.primary`: tracked right grip, actual right trigger scalar/boolean,
existing stream nonce/sequence, original publication and status history.
[OpenXrInputPlugin.cpp](../../../../android/vr/pico/apps/picoInterface/openxr/src/OpenXrInputPlugin.cpp)
consumes the actual action/pose states. Its original right-trigger float at
least 0.95 also produces RT_VIRTUAL_CLICK (lines 1392–1401); a boolean-layer
ACK alone cannot prove that mapper input. The ordinary entity-pointer path
reaches [RenderableWebEntityItem.cpp](../../../../libraries/entities-renderer/src/RenderableWebEntityItem.cpp)
`WebEntityRenderer::handlePointerEvent` and its actual TOUCH or MOUSE branch,
then the offscreen Qt window and
[NativeWebViewItem.cpp](../../../../android/common/web/src/NativeWebViewItem.cpp)
`mousePressEvent`/`mouseReleaseEvent` or the actual translated touch route.
`pointer` converts to image pixels and invokes original Java `pointer`;
[EmbeddedWebView.java](../../../../android/common/web/java/org/overte/web/EmbeddedWebView.java)
`input` gates the real owner, and `dispatchPointer` dispatches/recycles actual
MotionEvents. A computed aim or OpenXR publication ACK proves no hit/focus.
The selected input mode must be observed; one branch cannot certify the other.

Normal VR-keyboard delivery is
[Keyboard.cpp](../../../../interface/src/ui/Keyboard.cpp)
`Keyboard::dispatchKey` (line 652): actual press/release QKeyEvents go through
[Application_Events.cpp](../../../../interface/src/Application_Events.cpp)
`Application::dispatchVirtualKeyboardEvent` (line 1075) and
`handleKeyEventForFocusedEntity` to the current original entity. The real
normal dispatcher can restore its recorded target when focus is absent; the
new source must compare that actual target/focus with the current World
entity instead of assuming the requested keyboard target was consumed.
It is separate from an ordinary QInputMethodEvent. The selected native World
consumer handles both through `keyPressEvent` or `inputMethodEvent` (line 675),
then `editorCommand` (line 646), current `allowsEditorDocument`, original JNI
`edit`, original Java `input` gate, and the existing production
`__overteEditor.edit` implementation in
[editor.js](../../../../android/common/web/resources/editor.js).
That implementation has real beforeinput/cancellation/composition/edit logic;
a Qt handled event or JNI return cannot substitute for its observed effect.

The existing gated `installWorldWebTextProvider` in
[PicoE2eTabletBridge.cpp](../../../../android/vr/pico/apps/picoInterface/e2e/PicoE2eTabletBridge.cpp)
(line 490) sends a normal QInputMethodEvent to the actual focused window,
using the actual original text/cursor/anchor and existing range checks.
It does not traverse individual VR-keyboard keys. The future receipt must
state which actual route was consumed; a QIME proof must not claim VR keys.

There is a real InputConnection path in the separate
[PicoWebViewItem.cpp](../../../../android/vr/pico/apps/picoInterface/src/PicoWebViewItem.cpp)
`inputMethodEvent` (line 520),
[OffscreenWebView.java](../../../../android/vr/pico/apps/picoInterface/src/main/java/org/overte/pico/OffscreenWebView.java)
`editText`/`focusedEditor` (line 442), and
[PicoTextInput.java](../../../../android/vr/pico/apps/picoInterface/src/main/java/org/overte/pico/PicoTextInput.java)
`text`/`InputConnection.commitText`. It cannot establish consumption for the
selected shared World backend. No port, replacement backend or InputConnection
product repair is proposed.

## Existing observation gap remains exact

[PicoBrowserFeatureE2E.inc](../../../../android/common/web/src/PicoBrowserFeatureE2E.inc)
(lines 210–215) requires `_featureWebFinishedGrant == current grant` before
old `measure-ray` or `commit-text`. Retained foreground return rotates the
authority grant without a new finish, so those existing E2E paths refuse.
Their observe2/ray3/text4 bodies, Java handlers, versions and old callbacks
must remain byte-identical. No fake finish, extra reload, current-grant load
count, selector script or direct test-only DOM setter may bypass this gap.

[CurrentDocument1](WORLD_CURRENT_DOCUMENT.md) instead preserves the exact old
finish plus actual current native/Java bookends and one original readonly DOM
transaction. The future source must reference that native original query;
caller-provided identity/expected state cannot create its authority.

## Proposed closed protocol

Proposed name: `pico-world-current-input:1`, separate packet/property/TSI/probe
file (`feature-world-current-input.json`). `pico-world-current-document:1`
is unchanged. No new common version is selected by this proposal.

Every command has exactly these existing seven fields:
`schemaVersion:1`, `commandId`, `action:pico-world-web`, `runId`, `fixtureUrl`,
`operation`, `ownerToken`, plus the following operation-specific fields:

| Operation | Additional exact fields | Normal input |
|---|---|---|
| `measure-current-ray` | `documentNonce`, `control` | None; one readonly geometry request |
| `observe-current-focus` | `documentNonce`, `control` | None; one readonly focused-editor request |
| `commit-current-text` | `documentNonce`, `focusNonce`, `control`, `text` | One original QIME provider invocation after durable admission |
| `observe-current-consumption` | `documentNonce`, `attemptNonce` | None; original trace read only |

IDs are existing lowercase 32-hex nonce grammar; fixture URL/run/owner use the
existing exact admission. Control is the existing closed World control set.
Focus/text controls are only `text` or `foreign`; text retains existing
UTF-16/control/private-key restrictions and 512-unit bound. No caller point,
entity transform, DOM selector, JavaScript, native grant or fabricated finish
is accepted. A requested text remains an intent, never an observed value.

`documentNonce` resolves a retained native CurrentDocument1 query belonging
to this exact run/root/token/PID/source instance. A ready/fresh original is
mandatory before a new geometry/input query. The native cache reference is
authority; Python additionally retains complete source bytes and physical
original-file provenance. A document nonce cannot be rebound to a different
item, record, finish or logical DOM instance. `focusNonce` resolves the exact
new-protocol focus original under that same authority. Unknown/foreign IDs
fail before any Java query, event, provider or OpenXR publication.

Exact common packet header: `picoWorldCurrentInputVersion:1`, `commandId`,
`runId`, `ownerToken`, `documentNonce`, `instance`, `sequence`, `processId`,
`requestedEpochMs`, `requestedMonotonicMs`, `capturedEpochMs`,
`capturedMonotonicMs`, `status`, `source`.
Status is exactly `pending|ready|unavailable`. Pending/unavailable have
exactly `{}` source. Ready source is operation-dependent:

| Operation | Exact ready source fields |
|---|---|
| ray | `documentReference`, `originalFinish`, `authorityBefore`, `geometryRaw`, `worldRay`, `authorityAfter` |
| focus | `documentReference`, `originalFinish`, `authorityBefore`, `focusRaw`, `nativeEditor`, `authorityAfter` |
| commit | `documentReference`, `focusReference`, `originalFinish`, `admission`, `attempt`, `trace` |
| consumption | `documentReference`, `attemptReference`, `originalFinish`, `trace`, `authorityBefore`, `authorityAfter` |

Each `*Reference` is exactly `{commandId,instance,sequence}` resolved from its
native retained original. It is not a host-chosen semantic digest. The Python
owner links the full immutable originals, not merely those three fields.
`originalFinish` remains the exact six-field row, including old epoch/grant;
complete CurrentDocument1 documents/history remain linked as a full original.
Both authorities reuse CurrentDocument1's exact native/Java grammar, but are
two newly captured bookends, with their own unchanged clocks. Only semantic
authority fields compare equal. No old authority snapshot is copied as fresh.

`geometryRaw`/`focusRaw` preserve complete JNI wrapper/quoted raw geometry,
including new Java before/after bookends, and reuse the unchanged closed
`webGeometryVersion:1` readGeometry result. Its DOM instance/document must
match the resolved original document; sequence advances, historical attempts
and echoes retain exact prefixes. No focus/retry loop is hidden in a query.
`worldRay` reuses the existing `worldWebRayVersion:1` producer and complete
entity/QML/window/renderer/sensor projection grammar. It proves calibration,
not an actual controller hit. `nativeEditor` has the existing exact native
text/cursor/anchor/absoluteCursor/kind/sensitive/focused/enabled fields; its
observed state must agree with the independently read current DOM editor.

Commit `admission` is exactly `{checkedEpochMs,checkedMonotonicMs}` from the
actual last pre-delivery check. `attempt` is exactly
`{nonce,route,issued,issuedEpochMs,issuedMonotonicMs}`: route is `qt-ime`,
issued is an actual boolean, and clocks are null until an invocation really
occurs. This receipt distinguishes dispatch from consumption/effect. A
VR-keyboard action stays in its existing normal owner/controls and must
produce an actual `qt-key` trace; this commit operation cannot claim it.

A trace is exactly `{complete,records}`. `records` is a bounded ordered list
of originals with exact fields
`{sequence,eventId,stage,route,handle,creation,grant,page,url,sourceIdentity,payloadRaw,payloadSha256,capturedEpochMs,capturedMonotonicMs}`.
Stage is one of `qt-event-enter`, `qt-event-handled`, `native-editor-admitted`,
`jni-edit-issued`, `java-input-admitted`, `java-evaluate-issued`.
Route is `qt-key` or `qt-ime`. The complete raw event/serialized product-command original and its SHA come
from the actual consumed value at each corresponding boundary,
not an assigned requested-text copy. Qt-entry raw grammar is the actual
route-specific event data (key/type/modifiers/text, or commit/preedit/replace
and attribute data); subsequent JNI/Java stages retain the exact existing
product command JSON bytes. No raw data may be discarded for its digest. Correlation is an opaque out-of-band
native event ID plus actual identity/command bytes; it must neither add a
DOM field nor alter the product edit command. Missing/rejected boundaries
remain absent; `complete` means the bounded original trace acquisition is
finished, not that a desired edit succeeded. A ready receipt may consequently
have `issued:false` or an incomplete observed route; the journey refuses to
claim effect from it. Final field grammar and trace hooks require Root review
before implementation, particularly correlation across Java's actual queue.
The needed observers would be additive test-build/runtime gated hooks at the
actual Qt-handler predicate, editorCommand JNI invocation and Java normal
input/evaluate boundaries. They may record the actual evaluated predicate
and arguments but cannot add an admission bypass, skip the existing gate,
change an event/command, call a second edit or turn observer failure into
product-input refusal/success. Legacy text4's include/handler remains byte-
identical. No instrumentation is implemented by this document.

## Exact normal flow and distinct evidence

1. Acquire a genuinely new CurrentDocument1 original under the parent's same
   ScriptSourceLock. Its exact original finish and logical DOM identity are
   retained even across a current-grant rotation.
2. Resolve that nonce and query one passive geometry original under new
   current-authority bookends. Reuse actual existing projection, image/DOM
   aspect, effective visibility, item hit ownership, QML context/entity ID,
   local named Web entity, clipping/occlusion, sensor and tracked pose checks.
3. Parent journals the intended normal trigger and original calibration.
   Reuse the existing single OpenXR session/stage, its actual envelope and
   pure host before-publication callback. Publication is not target effect.
   Record every actual status, including held/unknown, and actual neutral.
4. After normal input, acquire a new CurrentDocument1 and new passive focus
   original. Require actual Qt activeFocus, current editor native callbacks,
   real Java owner/grant/page and independent DOM focus. Geometry observation
   cannot itself click/requestFocus/publish desired editor state.
5. Parent durably records the commit intent, then immediately revalidates
   exact native current authority/focus and original ages before one ordinary
   QIME provider call. For a VR-key route, keep the existing normal keyboard
   controls and observe their actual dispatch separately. No replay on lost
   response and no new retry operation is added.
6. New readonly original DOM/geometry and actual native/Java trace establish
   what was consumed and what changed. Native event handled/JNI issued/Java
   evaluation issued remain delivery observations, never a changed editor,
   network echo, successful navigation, HTTP receipt or stereo observation.
   Independent HTTP/Actor/current-runtime/PNG joins remain required later.

The existing input.primary plan includes a 1200-ms tracked approach and an
800-ms trigger interval. A 1500-ms calibration admission is checked at actual
stream publication; the later multi-second action/neutral history must not
be squeezed into that same old query or retimed. Every subsequent passive
query has its own real fresh clocks. Historical trace/event times remain
historical; they are not rewritten to the later acquisition time. A new
CurrentDocument1 for focus/consumption does not replace the older input's
immutable calibration/intent or authorize replay.

## Thread, weak ownership, clocks and query bill

A new operation's clock starts before the bounded V8→Qt dispatch, unchanged
through Java main queue, raw callback, packet/copies and actual outer source-
lock release. Native/host age is at most 1500 ms; future skew remains250 ms.
Original finish epochs are historical, not fresh-clock candidates. Expired
source/geometry/focus refuses new input; an old receipt may only be validated
as historical against its own original clocks and unchanged owner lineage.

Qt/item/window/context/entity/dependency access remains on the original
owner thread, checked before dereference. Native item and Java instance/host
captures are weak, with a separate bounded queued receiver as in032. A
single outstanding input may have a retained unresolved original record;
no timeout, weak death or foreground change can clear its issued fact or
allow replacement delivery. Current item, source, page, creation, grant,
original finish, logical DOM and QML/entity geometry must be revalidated
before delivery and on original callback acceptance. A genuine recreation
requires a genuinely new finish/creation lineage and cannot borrow a
retained-page lease. Old callback nonces cannot enter a new handler.

Proposed per-process bounds: 32 scopes, 128 operations/scope, 128 input attempts
per scope, 256 trace records per attempt, 4096 operation anchors; no silent
eviction. Existing CurrentDocument1's separate 128 queries/scope remain
unchanged. One ray/focus nonce performs exactly one Java readonly query;
same-nonce polls read retained originals only, never start another DOM read
or reset a clock. The existing legacy focused 20-ms retry helper is not used.
Raw JNI ≤16 KiB, geometry ≤8 KiB, output ≤64 KiB; full linked originals and immutable
trace chunks use existing 512-frame/16 MiB ownership bounds, without raising
limits or dropping a sample. Failure at a bound remains unavailable/owned.
All full originals and query counts must be reported by the owning case.

## Required disjoint original-body proofs after review

| Case | Required actual evidence, no inferred effect |
|---|---|
| retained/current grant | Old2/3/4 still refuse; current source/geometry has exact old finish and same DOM, no extra finish/load/clear; ordinary trigger can actually focus before QIME |
| real recreation | Real new owner/creation/page/finish; old lease/query cannot calibrate or type; a newly acquired original may admit the new lineage |
| stale grant | Foreground rotates grant between calibration and actual event publication/Java queue; input refuses or remains issued-unresolved, no retry |
| changed page/source | Real acceptPage/source transition invalidates old lease, geometry and editor before provider/SDK; unchanged old raw remains archived |
| foreign nonce/owner | Wrong run/token/documentNonce/focusNonce/callback allocates no authority and performs zero new DOM/input calls |
| weak death | Original item/context/Java registration removed before queued read/commit; actual receiver deferred deletion and retained record, no borrowed survivor |
| late/future clocks | Actual queued/provider/Java callback delay and real outer-exit Native+2000/−2000 with frozen host; host+2000 with frozen native; no new frame/time reset |
| delivery versus effect | Qt accepted/JNI issued but Java focus/authority loses or beforeinput cancels; actual consumed originals retained, unchanged independent DOM must refuse success |
| lost applied return | Real normal input reaches the original consumer, response lost; cold inspection keeps issued attempt and original source/raw, zero second trigger/QIME |

These are targeted existing host/native-body seams, not device evidence or a
second journey. They must be attached to the existing continuous World owner
and its actual independent Actor/HTTP/stereo/return/cleanup chain after source
review. The retained Common16 step15 mismatch and future explicit common
version dispatch remain separately open; no full 19-step qualification follows
from this native source capability.

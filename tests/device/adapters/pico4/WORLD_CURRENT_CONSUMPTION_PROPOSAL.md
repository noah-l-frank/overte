# Proposed current World input-consumption source

This is a source/protocol plan for Root review, not an implemented operation
or capability. Fixed Parent `16e0356b03` ends at real focus, with its original
text action still acting. No trace hook, Common migration, key/clipboard
setter or product behavior change is included by this document.

## Proven original dispatch and encoding boundaries

The actual bodies at this fixed source establish these separate edges:

| Original source | Actual behavior |
| --- | --- |
| `Keyboard.cpp:261–271` | PointerManager signals use Qt AutoConnection. Upstream pointer delivery can be queued; do not carry a borrowed PointerEvent across it. |
| `Keyboard.cpp:672–777` | handleTriggerBegin finds the actual key in the active layer, gets its original key string/scan code, and calls dispatchKey. Normal character keys dispatch individually; `_typedCharacters` only maintains display text. |
| `Keyboard.cpp:652–669` | dispatchKey creates two real stack QKeyEvents and synchronously dispatches press then release. HUD input is a separate branch. |
| `Application_Events.cpp:1034–1098` | Actual focused entity selects its event handler; sendEvent targets its QQuickWindow synchronously. Requested target, actual focused entity, handler/window, acceptance and after-focus are distinct observations. |
| `RenderableWebEntityItem.cpp:680–685`, `qml/OffscreenSurface.cpp:302–303` | The actual Web renderer returns its surface event handler, which is the original QQuickWindow. No legacy InputConnection is on this path. |
| `Keyboard.cpp:796–824` | handleTriggerEnd restores the key entity/pressed state/timer/selection. It does not generate the Qt KeyRelease; that already happened in dispatchKey. |
| `NativeWebViewItem.cpp:655–688` | keyPressEvent and inputMethodEvent are distinct consumers. They call the existing editorCommand subject to unchanged predicates. Accepted Qt input does not imply JNI/Java/DOM consumption. |
| `EmbeddedWebView.java:697–707`, `:145–173` | edit enters JNI synchronously, then input/post queue work to MAIN. Existing instance/owner/input-ticket/foreground/window/document gates run before the unchanged product editor JavaScript dispatch. |

The native helper at `NativeWebViewItem.cpp:68–77` uses NewString with the
actual UTF-16 units and GetStringChars/QString::fromUtf16 in reverse. It does
not use JNI Modified UTF-8. The observer must compare raw UTF-16 code units,
not GetStringUTFChars bytes. Java entry will receive an ID using its exact
original arguments and carry that immutable ID separately through its existing
queued lambda; neither product command nor product arguments carry the ID.

Native JNI-entry records read the already-created actual product jstring.
Record its exact length and UTF-16 units (explicit big-endian hex, no charset
replacement), and standard UTF-8 obtained from those actual units. Java records
its original `command.charAt(i)` units by the same explicit unit encoding and
its actual `getBytes(StandardCharsets.UTF_8)` bytes. No JSON reserialization is
used for correlation. Any codec disagreement remains unavailable. A counter
with non-ASCII and supplementary characters must reject ModifiedUTF8-based
correlation; malformed-surrogate behavior is retained and never normalized
into a match. Unicode/Qt-ime evidence is explicitly not VR-key evidence.

## Default 3D-keyboard source inventory and concrete boundary

`Keyboard.cpp:350–351` loads the original
`resources/config/keyboard.json` through loadKeyboardFile. Its SHA-256 is
`201aa79dd231327d3359a38bf5b86ea3edb253b8ddf17f6ef465682ffd937e50`.
The actual JSON-decoded inventory, recursively inspecting all key strings:

| Layer | Keys | Character keys | Other existing key types |
| --- | ---: | ---: | --- |
| 0 | 40 | 27 (a–z and space) | Backspace, caps, close, enter, select-all, cut, copy, paste, four cursors, layer |
| 1 | 40 | 27 (a–z and space) | Same existing special types |
| 2 | 44 | 31 (ASCII numbers/punctuation/space) | Same existing special types |

Every decoded key string is ASCII. `Keyboard.cpp:1068–1081` copies each actual
JSON `key` into Key; getKeyString only applies existing uppercase handling.
This inventory is about the checked default source, not an observed installed
device layout. No new layout, keys, paste/clipboard contents or text setter may
be supplied to manufacture the shared Unicode checkpoint. ASCII normal-key
consumption can be proved; arbitrary Unicode from Qt-ime cannot establish that
this default normal 3D keyboard generated it. Whole qualification stays open.

## Separate gated Trace1 grammar (proposed)

Leave CurrentInput1/CurrentDocument1, observe2/ray3/text4 and Common16 unchanged.
Use a separate private `pico-world-current-consumption:1`, only registered after
both operations below exist. Property/getter/file names will be separate from
the readonly CurrentInput1 endpoint. Action remains `pico-world-web`.

Every command has exactly schemaVersion=1, commandId, action, runId,
fixtureUrl, ownerToken, operation, plus its operation-specific keys:

| Operation | Additional exact keys | Meaning |
| --- | --- | --- |
| `arm-current-consumption` | `focusNonce` | Resolve the actual ready native CurrentInput1 focus query; no supplied focus, text, coordinates, identity or desired effect. |
| `observe-current-consumption` | `attemptNonce`, `afterSequence` | Read the next original frame after a cursor. This does not consume an input or delete a frame. |

Nonces are 32 lowercase hex; observe query nonce differs from attempt nonce.
The normal existing run/owned fixture URL/owner grammar applies. afterSequence
is a JSON integer (no bool/subclass), in 0–16. Invalid/unknown ownership refuses
without manufacturing a scope. Same query nonce requires byte-identical command
and the same original clock; it cannot read another frame, rearm or renew expiry.

Header is exactly picoWorldCurrentConsumptionVersion, commandId, runId,
ownerToken, instance, sequence, processId, requestedEpochMs,
requestedMonotonicMs, capturedEpochMs, capturedMonotonicMs, status, source.
Status is exactly pending/ready/unavailable; pending source is exactly `{}`.
Ready source has exactly attemptReference, focusReference, nativeBefore,
nativeAfter, lifetime, frame, availableFrames, terminal. Unavailable adds
exactly `reason` to those keys; unavailable fields can explicitly be null when
the original owner can no longer be safely sampled. No null invents death.
Reason is a closed enum: expired, weak-unavailable, authority-changed,
source-changed, event-overrun, raw-overrun, wrong-thread, incomplete-dispatch.

attemptReference is exactly nonce/itemInstance/sourceInstance. focusReference
is exactly commandId/instance/sequence of the actual native cached focus packet;
the Host binds the separately retained full original focus request/raw/Doc.
nativeBefore/After are two actual new CurrentDocument-native snapshots, never
copied. lifetime has individual actual item/context/window/receiver liveness
and active-attempt flags. Source absence is not resource retirement.

Arming resolves the native cached focus query and verifies every original
run/token/root, exact Native finish, current authority, logical DOM source,
valid original weak item/context/window and nonsensitive focused editor.
Only actual owned World fixture scopes are armed. There is one active attempt
per actual original item; it cannot bind another field/grant/page/source.
Arming is E2E recorder state only: no focus, input, DOM read, timer, reload,
product setter, changed predicate or expected-text field.

## One actual owner, threads and out-of-band event correlation

The registry has one implementation in the NativeWebViewItem TU owned by
picoOpenXR; exported declarations only in a neutral test-native header. Interface
Keyboard/Application and native/Java callbacks use that same owner. Query clock
factory likewise has one exported definition in the existing picoOpenXR TU,
started before TSI queued dispatch, with the original pointer checked natively.
Use the proven bounded weak queued getter; no BlockingQueuedConnection.

All QObject/QEvent dereferences occur on their actual Qt application thread,
with thread rejection before QPointer access. Weak item/context/window/receiver
checks precede and follow collection. Java callbacks carry only immutable
IDs/original argument strings and clocks, never a borrowed event or raw item.
MAIN callbacks queue their raw result back to the actual weak Qt receiver;
late/dead/changed-owner callbacks remain unavailable originals.

At dispatchKey, a short-lived registry entry binds each real press/release
QEvent pointer, type and native event ID to the actual requested World entity.
An optional enclosing actual handleTriggerBegin observer scope supplies the
real selected key entity/type after all original key/timer/pointer gates.
Without that original caller scope the origin is only keyboard-dispatch,
not a proved VR-key trigger. The observer never invokes that caller.
Application records the actual focused entity/handler and accepted result.
Native key/ime entry resolves the actual live event pointer and item; no
content-only guess or pointer-reuse fallback can create a Keyboard origin.
Unattributed Qt-key and Qt-ime remain distinct origins. HUD and unarmed
input are not collected. Actual
ignored release/press/modified keys are retained, never called consumed.

At the original JNI `call("edit",...)` entry, attach the ID only to recorder
state keyed by the actual item identity/current scope and exact original
handle/grant/page/URL/product-jstring units. Java may query that passive ID
with its exact original arguments at method entry, before any MAIN queue.
The existing lambda carries it in a separate local final value. Record its
actual acceptance immediately before the original evaluateJavascript only
after every unchanged post/input/edit predicate passes. The same product
JavaScript, arguments, null callback and dispatch count remain unchanged once.
That record means dispatched, not executed or edited. New CurrentDoc/geometry/
native editor originals provide the independent later effect.

## Full originals, bounds, closure and owning cases

Each frame is exactly sequence/eventId/kind/origin/epochMs/monotonicMs/raw.
Kinds are keyboard-event, application-target, native-input, jni-command,
java-entry, java-consume. raw is the full closed kind-specific original DTO,
with explicit UTF16/UTF8 fields only on command-bearing kinds. It is never a
requested/normalized verdict. Proposed caps: 16 frames/attempt, 8192 UTF-8
bytes/frame, 128 attempts/run, 32 runs, 4096 query anchors, 16 MiB global owned
raw budget, 64 KiB emitted packet. Refuse/incomplete on overflow; never evict
an owned original or silently truncate to success.

Exact proposed raw DTOs (no arbitrary QVariant/Java object export):

| Kind | Exact raw keys |
| --- | --- |
| keyboard-event | keyboardObject, keyEntity, keyType, eventType, key, modifiers, textUtf16Hex, requestedEntity |
| application-target | eventType, requestedEntity, focusedBefore, handlerMatchesWindow, focusItemMatches, handled, focusedAfter |
| native-input | authority, editor, eventType, key, modifiers, textUtf16Hex, commitUtf16Hex, preeditUtf16Hex, replacementStart, replacementLength, attributes |
| jni-command | handle, creation, grant, page, url, sourceIdentity, commandUtf16Hex, commandUtf8Hex |
| java-entry | handle, grant, page, url, commandUtf16Hex, commandUtf8Hex, isMainThread, capturedEpochMs, capturedElapsedMs |
| java-consume | handle, grant, page, url, commandUtf16Hex, commandUtf8Hex, before, after |

Origins are exactly vr-key/keyboard-dispatch/qt-key/qt-ime. UUID keys are actual
canonical entity IDs or explicit null where unavailable; keyboardObject is an
opaque weak-object association, never an invented construction time. eventType
is press/release for Keyboard/Application, key-press/ime for Native. Key/modifier
integers and UTF16 fields are actual consumer-used QEvent data; inapplicable
key/IME fields are null. attributes is the exact ordered list of original
type/start/length triples consumed by the existing IME body; it does not export
unconsumed arbitrary QVariant values. editor uses CurrentInput1's exact native
editor grammar, authority its exact native grammar. Java before/after reuse
the exact CurrentDocument Java grammar and are separately captured on MAIN.
Native weak-window and item comparisons are actual booleans, not pointer values.
Hex fields are lowercase, even byte counts; UTF16 hex must contain complete
16-bit units. No normalizer merges bool/int or malformed Unicode into a match.

Each observe emits at most one immutable original frame and its actual high
water mark; it therefore cannot grow a whole inline history beyond the private
cap. Existing Parent/source-chunk mechanics retain every acquired raw frame,
including unusable/stale/foreign frames before refusal. A cursor is a request,
not proof that the Host consumed or retired anything. Old records remain owned.

Each query retains its original prequeue anchor and 1500-ms/future-skew limits
through parse/copy/actual outer exit. Attempt expiry is a separate fixed
5000-ms monotonic recorder bound beginning at arm dispatch, never a product
input lease or renewal; no QTimer/retry is introduced. Later input events are
historical originals under their actual event clocks, not fresh calibration.
Queries preserve old captures. Exact changed grant/page/source/DOM/weak owner
cannot be repaired by another key, new nonce or fabricated finished event.

Owning evidence will use original Keyboard dispatch, Application routing,
QQuickWindow/Native key and Qt-ime bodies, actual JNI and original Java
edit/input/post bodies, with explicitly declared Android/UI dependencies.
Cases must include normal ASCII Keyboard press/release to the real selected
native consumer, release-unhandled truth, Qt-ime Unicode separately, exact
UTF16 versus ModifiedUTF8, same-nonce no-reread, wrong scope/field/grant/page/
nonce, delayed queue/clock, sensitive editor, weak death and original late Java
callback. Product dispatch must remain once even if the observer expires.
Full device/OpenXR/scene/Actor/Keyboard-Unicode/retirement claims remain open.

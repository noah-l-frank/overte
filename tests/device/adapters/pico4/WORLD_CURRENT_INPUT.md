# Readonly World current ray/focus and normal Session publication

`pico-world-current-input:1` implements exactly two operations:
`measure-current-ray` and `observe-current-focus`. The source is native-only,
Pico/test-build/runtime gated, private, and read-only. It does not implement
`commit-current-text`, consumption traces, a new journey, Common version, BG
replacement, public feature or complete World qualification. The reviewed
[proposal](WORLD_CURRENT_INPUT_PROPOSAL.md) still describes later, unimplemented
operations; this document and code define the actual implemented subset.

## Exact source and original ownership

Commands have exactly `schemaVersion:1`, `commandId`, `action:pico-world-web`,
`runId`, `fixtureUrl`, `operation`, `ownerToken`, `documentNonce`, `control`.
Existing strict run/owner/URL grammar applies; IDs are 32 lowercase hex.
`documentNonce` must differ from the new query's nonce. Ray controls reuse the
closed World control set. Focus controls are only `text` and `foreign`.
No caller supplies points, grant/page/creation, JavaScript, selectors, expected
text/focus or a fake finished event.

The native `documentNonce` resolves the actual retained
[CurrentDocument1](WORLD_CURRENT_DOCUMENT.md) query, not a caller DTO. Native
checks its complete original scope/token/root, exact original finish record,
logical DOM instance, live original item and document history. The original
finish epoch/grant is never rewritten. New operations have their own exported
anchor factory in the existing single picoOpenXR-owned TU, before queued TSI
dispatch; no header-local cross-library registry is introduced.

Exact result header: `picoWorldCurrentInputVersion:1`, `commandId`, `runId`,
`ownerToken`, `documentNonce`, native scope `instance`, `sequence`, actual
`processId`, immutable `requestedEpochMs`, `requestedMonotonicMs`, actual
`capturedEpochMs`, `capturedMonotonicMs`, `status`, `source`.
Status is exactly `pending|ready|unavailable`. Pending/unavailable source is
exactly `{}`. Completed unavailable replies are retained unchanged on polls.
Ready ray source has exactly `documentReference`, `originalFinish`,
`authorityBefore`, `geometryRaw`, `worldRay`, `authorityAfter`. Ready focus
source replaces `geometryRaw`/`worldRay` with `focusRaw`/`nativeEditor`.
`documentReference` is exactly `{commandId,instance,sequence}` of the actual
native original; Python retains and validates the full original bytes too.

Both authorities reuse CurrentDocument1's exact native/Java grammar and are
new captures, with distinct original clocks, not copies. Semantic authority
must match the original document and both current bookends. Native pins the
actual weak item, window and valid QML context/source association before
Java dispatch and rechecks them after callback/provider work. The original
WorldRayProvider supplies existing actual entity/QML/window/DPI/sensor
geometry. It cannot focus/click/move a target. JNI callbacks are distinct from
old handlers and bound to the actual new nonce/run/handle/creation/grant/page.

`geometryRaw`/`focusRaw` retain complete JNI JSON with exact `before`,
`geometryRaw`, `after` fields. The inner string preserves the complete quoted
existing `webGeometryVersion:1` readonly `readGeometry` result. Its logical
DOM/document must match CurrentDocument1 and its actual observation sequence
must advance. UTF-8 limits apply before parsing: inner 8 KiB, JNI 16 KiB, full
packet 64 KiB. There is no silent truncation, focused 20-ms retry, `focus()`,
requestFocus, DOM clear, reload or setter in either observer.

`nativeEditor` has exactly `text`, `cursor`, `anchor`, `absoluteCursor`,
`kind`, `sensitive`, `focused`, `enabled`, captured from actual native editor
state. A sensitive editor is unavailable. The requested control's observed
DOM focus and native current editor must agree; otherwise association is
unavailable. An initially unfocused native item/control can be observed as
false. No true focus is assigned from a requested operation or input ACK.

Per-process bounds: 32 native scopes, 128 operations/scope, 4096 current-input
anchors, 4 callback originals/query. Existing document bounds remain unchanged.
Same-nonce polls issue no new Java read and never reset an anchor. Raw failures
remain bounded native originals; weak death/expiry does not authorize another
input. A real recreation may reuse an object-local creation revision, so its
actual new handle/itemInstance/DOM instance and new exact finish establish
lineage; numeric revision alone is never called a new object birth.

## Shared source lock and ordinary input

`PicoWorldCurrentInput.read` first performs a genuinely new CurrentDoc.read,
then one geometry/focus query. Both share the exact parent's ScriptSourceLock
and host clock and both finish after real outer release. Already-held entry
is refused. Full parse/copy/seal work precedes final guard/native/host clocks;
all original source clocks are checked, including geometry and the linked
original document. The immutable warm anchor covers both acquisitions. No
later sample replaces an old admission timestamp.

Private Pico factories `_world_current_input_originals` and `_world_current_ray`
reuse the actual native observer, original private debug files, original
candidate/PID/foreground guards, exact same lock, and existing
`PicoOpenXrAdapterSession`. A parent must delegate source reads outside an
already-held lock. No public CLI action or parallel input session is added.

`PicoWorldCurrentRay.publish` consumes a sealed, warm ray original. It writes
the parent's durable intent before ordinary input, persists the actual
Session envelope through the existing intent hook, and applies pure host
elapsed/byte/CAS checks in the existing `before_publish` callbacks. The
binding performs its supplied exact phase admission outside the Session lock.
The envelope remains the existing `input.primary` command with calibrated
pose only; no invented document lease is passed to OpenXR. Source/clock/SDK
queries cannot reenter its locked publication callback.

The SDK receipt remains labelled `publication`. It is not a hit, focus, editor
value, HTTP echo, native consumption or World verdict. The existing plan has
1200-ms approach plus 800-ms trigger. Later stream events remain historical;
a new post-input source read gets a genuinely new nonce/clock. `check_focus`
requires fresh, independent native/DOM focus under the exact original
calibration authority and finish. A changed grant after publication remains
issued/unresolved, even if a new readable current document exists. A lost
applied return retains parent/stream originals and cannot resend.

## Verification seams and open normal keyboard path

The complete original NativeWebViewItem/JNI source, actual WorldRayProvider,
RayPick projection and renderer mouse body execute in the Qt5 native test.
Its real Qt pointer reaches the original native/JNI consumer and actual Qt
focus. The declared Android view/DOM model consumes that received JNI pointer;
subsequent native editor callbacks and new document/focus source read its
observed state. Entity/avatar/HMD and Android DOM/editor are explicit host
boundaries. No OpenXR device/mapper or independent HTTP/render effect is
inferred from that test.

Disjoint original-body cases cover unknown/colliding nonce, actual grant/page/
source transition, item death, real new object/finish/DOM lineage, owned QML
context destruction, window detachment, real delayed callback and actual
occluding Qt overlay. Every failed original is retained; no extra target
read/pointer or input replay is accepted. The complete actual TSI getter is
compiled on both Pico/non-Pico sides with its actual exported factory and
bounded worker/late-clock checks. Separate Java tests execute original
geometry/owner/bookend methods with actual WebDocumentState/JSONObject and
explicit Android/JNI seams; no focus/retry methods exist in the view fixture.

Python proofs use the real existing Session and original envelope compiler/
query consumer with explicit controller/DOM models. Publication alone leaves
focus false. Only consumed pose/trigger queries, independently projected to
the model control, change its state; then new source originals show focus.
Pure locked hooks reject slow CAS/SDK publication with frozen native clocks.
Reader real outer-exit native+2000/−2000, host+2000, changed guard and final
parser delay reject without another input. Actual Pico private-factory tests
verify the exact parent lock, old session, private source paths and no extra
normal UI/controller delivery.

The actual VR-keyboard route is still **open**: `Keyboard::dispatchKey` sends
QKeyEvents through `Application::dispatchVirtualKeyboardEvent` to the selected
entity. The selected shared NativeWebViewItem consumes Qt key/IME events via
its production editorCommand/JNI/Java editor path. The separate legacy Pico
OffscreenWebView InputConnection cannot qualify it. No Qt-key or Qt-ime
consumer trace hook, commit operation or VR-keyboard qualification is included
here. The next trace packet needs the reviewed activeAttempt/eventId/exact
product-command out-of-band correlation at actual Qt/JNI/Java consumption;
product arguments, predicates and dispatch must stay unchanged exactly once.

Old observe2/ray3/text4, featureRead, CurrentDocument1 and Common16 remain
readable and semantically unchanged. Independent Actor/HTTP/stereo, full 19
steps, versioned BG dispatch, normal Script/VM/source/host retirement and
public coordinator remain separate open joins. No owned original is dropped
for Phone's first/latest storage strategy; fixed Phone architecture may be
reviewed later without copying Touch/Mono authority or selecting Common17/18.


## Fixed packet evidence

The final implemented source selection passed **14 cases / 22.487 s**:
original Java bodies, complete Native/JNI plus Pico/non-Pico TSI getters,
ten disjoint original Native counters, and twelve reader/publisher/private
factory cases. Source freeze
`6c747167bfde88ef009c7cbe0c94df8a802d10c4c35d4ed4716d60728d27474b`
contains **13,556** tracked/new source files. The reader also combines original
clock skew with actual outer-exit host age; a 200-ms original offset plus a
1.4-second frozen-native-clock exit is refused without another query/input.
The model, Java and Native stages are retained from their initial creation.

The appropriate old-source selection passed **13 cases / 27.552 s** on
preceding freeze
`928f86cda1a3e0d60d83b03f0c82d8a22db884c4f049117e715b3f38311d7918`:
CurrentDocument Native/reader/Java, the actual production Java API compile,
and both actual factory functions across two independently built hidden
RTLD_LOCAL DSOs. Old factory checks remain and new ray/focus checks are
additive. The only subsequent runtime change is the stricter new reader's
combined age fence; its added counter is in the final fourteen cases.
Nine whole old files/original function bodies were separately compared
byte-for-byte against fixed `0883f180f66c34efba4ce4b4de409ac780358d64`, including
old observe/ray/text implementation, featureRead, CurrentDocument source and
factory/getter, and Common16. Four repository checks passed **2.84 s**;
coverage ten cases, strict version registry, Node syntax and diff checks pass.

Earlier private stages remain evidence of real harness/source corrections:
an identical std::function provider alias collided with Qt's existing
metatype declaration; the new provider is a distinct struct. Repeated failed
queries initially republished failure headers; completed unavailable replies
are now frozen. A recreated object's local creation revision was incorrectly
assumed globally unique; the assertion now uses actual new handle, native
item/DOM instances and exact new finish. Narrow compile failures in new host
logging/provider namespace bindings were corrected before final verification.
No prior failed run is presented as green or as a product/device observation.

Dependencies are the fixed CurrentDocument1 chain `032419eecc`, `d577a54728`,
`0883f180f6`; proposal `d5050e2ef0` is documentation only. This packet adds one
private contract registry entry and three selectors
`world-current-input-native`, `world-current-input-java`,
`world-current-input-reader`, all mapped to existing Web rendering/input risk.
Its local catalog delta is **+3**; integration must retain every newer Root
selector/version entry. It adds no public feature/capability or Common version.


### Review follow-up: exact field and scope at focus resolution

A real two-source model transition reproduced a publisher-join defect on the
fixed `117d6aded4818f383655e1267661e4f73e1bf1bc` publisher. A new original
CurrentDocument response observed the text editor focused. Before creating
the subsequent independent geometry/native-editor response, the model's
current focused field changed to the foreign URL editor. The actual new
request/control was `foreign`, its native kind was `url`, and every strict
source/DOM/original-finish check passed. The old resolver incorrectly accepted
it for the original text ray (one counter failed: expected refusal not raised,
**.054 s**). Neither original was rewritten to manufacture the mismatch.

Focus resolution now requires exactly the calibrated `control`, `runId`,
`ownerToken` and `fixtureUrl`, and only a calibration for `text` or `foreign`
may resolve editor focus. Ordinary publication for other closed controls is
still allowed; its publication never becomes an editor-focus proof.
The actual before/after source grammar, original authority/finish comparison,
warm source fence and no-replay rules remain in place.

The thirteen reader/publisher/private-factory cases passed **1.112 s**, source
freeze `e28781649459d177c688a01aa68d0cce28298b0277a739d5e725757874caff5b`.
That includes the new transition and unchanged ordinary Session/no-ACK,
slow-publication, changed-grant and lost-applied-return counterexamples.
The new case archives its full calibration/envelope/focus originals before
refusal. The first red retained source manifest, log and actual input intent/
envelope, but had no separate focus-original file; the fresh green run adds
that evidence write without reconstructing the old packet. Native/Java bodies,
contract/catalog and the separately retained Parent WIP are not in this fix.


### Review follow-up: observe the calibrated field, not always `text`

The actual `web_dom_observation.js` document `read()` always samples the node
named `text`. A separate positive producer case calibrated `foreign`, consumed
the actual compiled normal ray/trigger model, then independently generated a
new foreign geometry/native-editor response (`kind:url`, focused true) while
its full new document original correctly retained text focus false. The fixed
439 publisher rejected that valid source (**1/.050 s**, complete original
bundles retained). No old response was edited to make it pass.

The resolver now reads focus from the exact requested control's original
geometry and native editor. Full document identity, original finish, exact
calibration control/scope, strict raw grammar and final warm fence remain
mandatory; the document's unrelated text-field focus is not an input verdict.
Fourteen reader/publisher/factory cases passed **1.210 s** on source freeze
`c5b27811bc515416b31880861abe0eb52eb718bc907b016a1e99479501472f53`.
The prior mismatched text-to-foreign counter still refuses. No Native, Java,
Parent, public surface, shared version, catalog or Keyboard hook changes here.


### Review follow-up: every original clock before publication

A separate actual producer case generated Java before/after wall-clock
captures 200 ms before the native clock, within the existing 250-ms allowance.
The new original Doc DOM/geometry clocks remained within their allowed
bookends; no accepted packet was modified. A landed stream-intent CAS then
advanced only the host clock by 1.4 seconds. On fixed `a624e803c7` the locked
callback incorrectly used only requested header clocks: it sent one actual
model envelope, then refused at the later full-source fence (**1/.049 s**).
The complete calibration/raw transactions, stream intent and actual emitted
envelope remain archived. A post-publication failure is not prevention.

The pure locked callback now starts from the sealed earliest original among
both Doc/Input requested/captured headers, every native/Java bookend, Doc DOM,
geometry and ray captures. That immutable bound is computed and validated
before any input intent or SDK lock. Both existing host-only callback checks
cover elapsed CAS/SDK/publication work against the same 1500-ms limit; they
perform no SDK, source or native clock read and never renew an anchor.
The unchanged real Session rejects the skew-plus-slow-CAS case before any
envelope is emitted. All fifteen reader/publisher/private-factory cases passed
**1.243 s**, source freeze
`7836a6bbe7789732b69438130af2c2db7b1523a3b72b48a295b99927d05fe9a1`.
No Native/Java/Parent/schema/catalog/shared-contract change is included.

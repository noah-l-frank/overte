# Proposed versioned World lifecycle continuity

This is a review proposal, not an implemented or accepted contract. Shared
Common v16, its original nineteen actions, old owner readers and native getters
remain unchanged. The current Pico first-14/stereo/source-return packets remain
partial. No product foreground/loading behavior, manual Reload or synthetic
finish event is proposed.

## Fixed evidence and Phone comparison

The actual original-body Pico counter in
`23e8183d5f6ba09c12944bca24fba719259ff46f` calls real nativeForeground(false/true).
Native handle/creation/page and the original finish remain, the actual current
grant advances, and the old World getter stays pending without a Java DOM
query. [The source audit](WORLD_WEB_RETAINED_RESUME.md) found no guaranteed
HOME/Activity/Qt lifecycle-driven recreation. That is legitimate retained
product behavior and an observation/contract mismatch, not proof of recreation.

Read-only Phone reference is exactly
`a7be274da152b9d0b77e2fe5bb9874c5b1e18a31` (assessed runtime
`7be78768fa023ea88eada5ddfabd1189ff9d665f`), not a moving branch. Its
WORLD_WEB_FEATURE.md and TABLET_WEB_FEATURE.md describe full normal v17 host
compositions and separate actors/finalization; source/host seams and missing
Android/device integration are disclosed. Useful architecture is normal Script
entry, original HTTP/DOM histories, actor credentials, ordinary input intents,
quiet and original ownership. Appium, Phone touch, native-screen Mono artifacts
and Phone retirement assumptions cannot qualify Pico.

Concrete relevant Phone code at that fixed object:

- `android/phone/tests/device/test_world_web_feature.py:81–85` models app.launch
  as creation++ plus load(source), except the old-resume negative. That is an
  explicit producer recreation seam, not an actual lifecycle observation.
- `android/common/web/src/NativeWebViewItem.cpp:469–474` retains created items on
  foreground return; it calls create only when not created.
- `android/common/web/java/org/overte/web/EmbeddedWebView.java:75–86` refreshes
  the current document grant and resumes/authorizes an existing nondestroyed
  view; `authorize:810–824` rearms the existing transports under current grant
  and page. It does not manufacture a new page-finished callback.
- `PhoneWorldWebE2E.inc` invokes featureWebDOMRequest; actual NativeWebViewItem
  lines 1026–1027 and 1082 still demand current grant == original finish grant.
- Phone scenarios.py:408–409 still categorizes background-resume as replace.

Thus this fixed Phone source does not already supply the required retained-
finish/current-grant proof. Its whole host result cannot substitute for the
Pico original-body counter. No Phone files are selected or modified.

## Proposed explicit contract version

Root should reserve the next compatible shared version after reviewing all
current users; in a Root still at v16 this would be a new v17, not silent use
of Phone Common18 or an in-place v16 change. Keep the nineteen normal actions.
Only new-version World background-resume chooses **document retained or genuine
new document**, from actual originals. Other replace actions stay replace.
Unknown/contradictory histories remain unavailable.

A new result must retain literal original evidence references for this choice,
not accept a requested branch or a boolean supplied by an input receipt. A
closed `worldLifecycleContinuityVersion:1` evidence capsule should contain:

| Field | Original authority |
| --- | --- |
| binding/owner/run/ticket | Original pre-input Parent and exact phase |
| before/after frame references | Full original role-owned source frame hashes/cursors |
| background/resume history references | Actual OS input ownership and passive Qt/Java/native lifecycle records |
| currentAuthority | Current handle, creation, grant, page, URL, actual Entity/source identity |
| originalFinish | The unchanged original completion-record identity and original event epoch |
| currentDOM | Fresh query nonce, DOM instance/sequence, href, response ID and complete readyState |
| document-history references | Complete bounded original finish/document and DOM/event histories |
| runtime references | Native-before / Java / native-after current ownership and live renderer |

All references are admitted against actual immutable files and complete raw
packets. The branch label is derived by the independent verifier. Old event
epochs are historical, never retimed or required to be freshly created. Fresh
current captures remain bounded by the existing native/host clocks, future
skew, physical originals, original installed process/session and final real
outer exit.

**Retained document:** same actual handle/creation/page/URL and original finish,
same original DOM instance/response ID, complete unchanged native document
history, new actual current grant and fresh native/Java/DOM association. No new
HTTP response, callback or document load is inferred. Focus/keyboard/lifecycle
are observed independently. Text is the actual retained DOM value; no setter
empties it to fit an expected checkpoint.

**Genuine new document:** an actual new original completion under its actual
new native document identity, complete original lineage to the owning Entity/
Script, fresh DOM/HTTP response and current native/Java association. Creation or
grant changes alone are insufficient. A new active native renderer is not by
itself a new document. No synthetic onPageFinished or explicit Reload is added.

Native completion events must remain literal. Count distinct original logical
documents, not observations or grant changes. In the retained branch, histories
under old/new grant can contain the same DOM attempts/echoes. Projection must
qualify their same actual DOM/document identity and unchanged byte prefixes and
count each actual event once; summing every grant-keyed DOM-history copy would
falsely double messages. All original copies remain archived. Duplicate finish
callbacks under a refreshed grant likewise cannot invent a new logical load.

## Additive Pico observation, no product repair

Add a separate, default-off Pico E2E observation mode/operation and closed
schema rather than changing old `picoBrowserVersion:2` semantics. Existing
observe, Tablet, Phone, old versions and nativeFinished/current-finish checks
keep their exact behavior. The new World-only source may pair a retained
immutable document finish with independently current authorization.

On the actual item thread it must select one original scoped finish matching
handle/creation/page/URL, snapshot the current session authority and source
identity, and issue the real read-only Java DOM request. The asynchronous reply
must still match that exact request, current handle/creation/grant/page/URL,
current owner and original finish. Fresh native/Java bookends must agree. A
changed source, ambiguous finish, destroyed object, foreign document, expired
query or old-grant callback fails. Original sources/queries remain bounded and
private, with actual process/testScript gates and weak lifetime ownership.

The old Pico geometry/IME provider also checks finishedGrant at
`PicoBrowserFeatureE2E.inc:214` and :239. The new mode therefore needs an explicit
current-authority geometry/focus observation carrying the same retained-finish
proof. Reuse the existing Entity ray calibration, actual controller delivery
and native InputConnection/IME path. Never weaken old operation guards, set DOM
text, synthesize handlers, change product acceptance or normalize a stale view
into a new one. If ordinary post-resume ray/IME still refuses in the product,
report that concrete boundary; observation compatibility is not permission to
repair product behavior.

Old native/Java DOM, bridge and editor callbacks must be exercised through their
actual original grant/page/request guards and shown not to change current
ledgers/state. Do not claim that arbitrary old OpenXR gestures carry a document
lease unless the actual consuming path records one. Normal later inputs must
be newly admitted from fresh current ray/geometry/IME originals and final phase
fences; uncertain prior delivery is never repeated.

## Migration and required review boundary

Current contract.py and engine.py import one global VERSION; old owner readers
also call its arguments validator. Merely incrementing that constant would
make retained v16 journals unreadable. Introduce explicit version dispatch and
freeze exact v16 scenario/argument/result/transition semantics before changing
current defaults. New run registration must record its selected contract/source
profile and return that original selection. Missing legacy discriminator stays
v16. Old journals are read-only; no guessed baseline, owner adoption, in-place
conversion or replay is permitted. New-version owners start only in an actually
available authorized scope. Phone v17/Common18 is a comparison, not a dependency
bundle or authority to migrate every feature.

New World history/stereo-source/owner DTOs must explicitly carry the new source
shape and read old versions without reinterpretation. SourcePass v1/v2 continues
to qualify only its original prefix/PNG/process scope. A future whole coordinator
must join the new normal 19-step sequence, both independent roles/current HMD
evidence and genuine resource/host/journal retirement. This proposal does not
weaken existing cleanup or declare alive VM/cache resources released.

Before code selection, review the exact new schema, version dispatch and source
thread/lifetime plan. Then require: old v16 strict replacement and old getter
counter unchanged; actual original-body retained-grant case with no fake finish;
actual recreation case with real completion; both independent roles; changed
finish/foreign DOM/PID/nonce; frozen clocks and late CAS/exit; genuine HOME/
resume history; later normal ray/IME/Send; actual stale-callback rejection;
unchanged message/load counts on retention; and full current stereo brackets.
No hardware runs or physical acceptance follow from those source/host proofs.

# Source compatibility review during adapter implementation

The fourteen-area extension has executable assertion logic and host
counterexamples. It has **no qualified product producer**. Native adapter work
has now exposed assumptions in several draft workflows that do not describe the
actual product UI. Host-model success does not resolve those mismatches. No
complete area capability may be advertised as implemented on that basis.

The current contract is version 13. Version 2 corrected Scripts to the ordinary
file-bundle picker and actual relative companion execution, with negative
cases for execution after cancellation, missing companions and frozen ticks.
Version 3 corrected Audio to its automatic memory-preview cycle.
Version 4 corrects Graphics to immediate actual controls and measured originals.
Version 5 corrects ordinary Emote override/chooser semantics, adds nine natural
completion checks and separately requires restoration before nominal clip end.
Version 7 corrects Chat channel/draft/transport semantics and separates local
echo from actual peer delivery. Version 6 corrects authentication view dismissal versus native request lifetime,
uses a real process restart to retire a delayed response consumer, and requires
actual delayed authority plus independent UI/error facts.
Version 8 corrects Create model URLs versus entity-JSON picking, actual export
DataVersion and the exact original texture slot.
Version 9 corrects Snapshot pending cancellation, private capture versus OS Save,
actual backend/authorization, system sheets and original external output bytes.
See [the explicit migration](feature_journeys/CONTRACT_MIGRATION.md).

These are test-contract corrections, not permission to add functional
product features merely to satisfy a test. The user has authorized E2E-only
instrumentation; functional product changes, builds and device runs remain
outside the current task. A changed published semantic contract must be
versioned before any complete area producer is enabled.

| Area | Actual reviewed source behavior | Draft v1 assumption requiring correction |
| --- | --- | --- |
| World/navigation | Places search filters actual directory records locally; named lookup emits not-found only for a real ContentNotFoundError. The draft inherits an open panel and old search results across a process restart. | **Correction pending.** Reopen the actual Places page normally before deleting the persisted bookmark; bind fresh page/search state and real owned place-name lookup failure. A missing serverless URL is not the named lookup 404. |
| Avatar/people | Avatar app Add Wearable creates a Model from the supplied URL and resolves Hips from actual joint names. Model::setURL deletes old geometry; Avatar::setModelURLFinished may load the bundled fallback while retaining the advertised failed URL. Bookmark restoration waits for onLoadComplete and then restores saved scale/entities. | **Corrected in version 12.** Observe actual geometry, advertised request and current-request failure independently. Use a real glTF Model wearable, not entity JSON or joint 63. Missing-model loading must remove A or show the actual fallback; recover via the ordinary saved bookmark without inventing a dismissible error. Mutual HTTPS connection consent remains a separate real-backend prerequisite. |
| Assets | AssetServer bakes FBX only, whereas the draft bakes glTF. Add to World requires a real extension, whereas the draft mapping loses it. The normal Delete control is disabled without write permission. | **Corrected in version 13.** Preserve primary extensions and complete relative mappings across actual folder rename; use the pinned self-contained FBX and original backend bake states. Disabled Delete must preserve mappings with no invented error. Remove an actually selected owned staged file before normal picker confirmation to exercise its real unavailable-file error; cancel leaves no upload. |
| Lifecycle/input | The draft carries Create text into subsequently opened Chat/Scripts editors and assumes common Back/keyboard outcomes without a reviewed active platform input profile. | **Correction pending.** Bind each actual editor and native keyboard/Back/lifecycle receipt separately before prescribing its text/focus outcome. Retain stale-context and world-input isolation requirements. |
| Authentication | `PhoneLoginState.h` explicitly keeps the account request alive when its view closes. `LoginDialog` destruction/dismissal and the generic overlay/tablet `tryDestroy` paths remove the view, without cancelling AccountManager. That manager owns its native reply independently. | **Corrected in version 6.** Close/reopen the still-pending request through normal controls, close again, then actually restart before releasing the old valid grant. Require fresh anonymous state in the new process and real delayed issued authority. Independent observations also include actual dialog/error state. Native logout clears local authority; backend fixture cleanup separately revokes retained tokens. Do not inject a functional network-cancel implementation to satisfy the draft. |
| Audio | `interface/resources/qml/hifi/audio/LoopbackAudio.qml` exposes one Record-and-Play button, automatic three-second in-memory capture/playback and cancellation. `AudioClient::startRecordedVoiceTest`, `finishRecordedVoiceTest` and its native timer own those real phases. | **Common flow corrected in version 3.** It checks automatic capture/play/drain/completion, native phase/history/frame relations, muted rejection and mute/background/cancel behavior, original input PCM and independent acoustic output. OS permission denial/recovery remains in the composed foundation. File recording is a different API; no Save/Preview/Discard control is invented. |
| Graphics on Phone | `scripts/system/+android_phoneInterface/phoneGraphics.js` restores a safe 0.65 default and accepts resolution 0.5..0.7. Its native settings switches/slider apply and persist immediately. | **Common flow corrected in version 4.** Freeze actual original preferences through independent agreeing observations, use common supported 0.5/0.6 viewport scales and real Haze/Mirrors controls, retain changes across close/restart and restore measured originals. Render-target/pass sources and actual visible controlled fixture joins are still missing; native settings alone cannot satisfy them. |
| Scripts | `Application::loadScriptURLDialog()` loads the submitted URL directly. `Application::loadDialog()` opens **Open Script and Companion Files** and loads the selected local source. `TabletRunningScripts.qml` provides the normal From URL/File controls. Entity-script consent is separate. | **Common flow corrected in version 2.** Native actual engine/require histories now exist on all three source branches. All three branches now have normal source-bound file-bundle controls and private original-byte staging/cleanup intent. Picker/engine ownership, restart handoff and the full companion/effect observer joins remain missing; URL foundations do not establish them. |
| Emotes | On the Phone adapter product base, `scripts/system/+android_phoneInterface/phoneEmote.js` selects a real bundled clip, calls the one-shot override, hides the tablet, and restores the rig on its timer. The common-base PhoneEmote copy does not hide the tablet; the desktop/Pico `emote.js` surface has different Sit/cancel behavior. Choosing the actually running startup script must precede binding an input recipe. | **Common flow corrected in version 5.** Ordinary plays require a native override; chooser lifetime permits the reviewed hidden/retained variants. Nine non-Sit clips must complete without cancellation. The explicit Waving abort requires native restoration before nominal end, with independent timing/peer facts. Sit reset does not claim that early-abort condition. Reopen the actual chooser as required and judge loaded/evaluated native clips, original poses/images and real peer effects. No product change is authorized to make a draft test pass. |
| Create | NativeCreate NEW Model supplies modelURL. Its Browse button opens Select .json to Import and invokes the ordinary Clipboard entity-JSON importer; it is not a raw glTF/OBJ picker. Application exports a new EntityTree whose persistence version is 0. GLTFSerializer names the pinned image texture checker.png. | **Corrected in version 8.** Test both normal model URLs, actual JSON picker open/cancel/accept, original exact-slot export, voxel changes and an actual create retry after domain rez recovery. Reject arbitrary texture-slot aliases, duplicate JSON and rewritten exported bytes. |
| Snapshots | Private capture does not need Photos permission; Android Save uses MediaStore or ACTION_CREATE_DOCUMENT without runtime storage permission. Photos Save requests add-only authorization. Share completion is handoff, not stored receiver bytes; the script has a short pre-render cancellation window and later hides the tablet temporarily. | **Corrected in version 9.** Measure a supported Save backend, require actual pending-to-cancelled history from a fast normal UI recipe, retain private capture despite denied Photos Save, inspect actual Save/receiver/upload originals, and witness actual system sheets/error/authorization. OS lifecycle/PID profiles and independent destination/cleanup actors remain unqualified; never simulate a missing OS API. |
| Chat | All three reviewed product bases use the same ArmoredChat JS/QML and MessagesClient source. There are Local/Domain tabs, separate histories and a 20-metre Local admission bound. Sending clears the editor immediately; native absence of a MessagesMixer emits local-only echo. No offline UI, retry queue or peer filter exists. | **Corrected in version 7.** Exercise actual channels, cancelled draft, distant Local rejection, stored history, original no-mixer local echo and explicit retyped resend. Observe remote delivery independently and allow two real local history rows after resend. Do not add product filtering/error/retry behavior to satisfy the draft. |

Additional source checks remain open, particularly the platform-specific private
Snapshot capture versus user export/share permission paths (corrected in v9). Create v8 corrects
the reviewed JSON/model/export mismatch; its full native picker/storage/entity
observer composition is still missing. Absence is not
inferred from a single source search. The remaining area drafts still require
their own final source/input/observer joins and independent actor evidence.

Implemented source packets remain useful and independently reviewable:
Phone's ordinary Create/Scripts foundations; Pico's ordinary native Script
foundation; iOS's explicitly unbound native Script component; and the shared
native lifecycle, evaluated animation/pose and memory-preview status sources.
Snapshot v9 now records supported original Save backends, cancellation history,
system sheets and original external files; see [its source contract](feature_journeys/SNAPSHOT_SOURCE.md).
They do not complete the fourteen version 13 triples. Required capability gates stay
closed, original compiler-dependent tests remain excluded from no-build runs,
and all physical qualification remains unperformed.

The [actual submitted Script-code identity](native/SCRIPT_CODE_IDENTITY.md) now
provides a source-bound prerequisite for choosing Emote input semantics. Seven
host profile checks include an execution of original tablet emote.js: its Sit
branch supplies an undefined endFrame, while non-Sit supplies a number. Native
conversion/pose behavior remains unqualified. This is a concrete source concern
to resolve before full Emote acceptance, not a functional change in this phase.

The [original Rig call/evaluated-pose history](native/ANIMATION_HISTORY.md) now
retains short-clip evidence after the live override ends. It distinguishes
native calls from actual loaded/advancing/changed pose frames, preserves original
timestamps and requires a later inactive evaluation after restore. It labels no
timer/button cause. Version 5 corrects the ordinary override and chooser
assumptions; full profile/input/history/image/peer joins are still missing. The
original Sit concern remains unresolved.

Version 10 corrects absent Chat channel and adds actual independent UI/resume fields. Version 11 corrects browser HTTP/foreign attempt/document lifetime and actual inline carrier semantics; [its source handoff](feature_journeys/WEB_SOURCE.md) separates those contracts from still-missing native sources/adapters.

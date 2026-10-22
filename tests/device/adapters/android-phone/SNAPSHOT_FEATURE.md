# Android Phone Snapshot adapter

## Guarded host publication

Snapshot role reads keep actual target checks at entry, immediately before
complete-frame publication and after publication. Every current native, render,
capture-file, saved-file, Documents, consumer and upload acquisition retains its
own original guards and deadlines. Private host transcript writes inside that
read use the exact source lock, unchanged feature-owner authority and role-header
compare-and-swap. They retain actual file hashing, inode/link/owner/mode checks,
fsync and durable planned/opened/saved stages. Outside that read, publication
continues to require the full target guard; exceptions cannot retain host-only
authority. No target facts or SDK responses are cached by this path.

A scoped native-producer fixture with actual private host files reduced repeated
target guards from 51 to 8 per capture read (0.451425 to 0.243107 host seconds).
Those are synthetic target-guard counts and host measurements, not Android
latency qualification. Four new counterprobes reject actual target changes after
binary/frame writes, preserve a foreign actual role header and prove failed
publication cannot leave authority for subsequent calls. The combined publication,
role, actor and facade union passed 50 cases in 35.785 seconds. Full common
MediaStore/document-picker and device qualification remain separate.

The separate [original capture-file owner](SNAPSHOT_CAPTURE_FILES.md) records
native FD/inode/close originals and independent binary acquisition, including
partial output ownership and one-send durable retirement. Its component sources
and host contracts are verified within the boundaries
documented below. The public facade, independent actor and strict retirement
are implemented; full common SDK29+ and SDK26–28 qualification is still pending.

The existing normal `snapshot.open/capture/files/close` implementation remains
the owner of the catalog's `snapshot-output-parity` foundation. It obtains
original files independently of input delivery. The current common contract is
**v18**. The Phone adapter contains the default-off
`feature.snapshots.act|observe|cleanup` triple and its guarded public dispatch.
Registration is source availability, not full qualification: both complete
Android backend replays, required foundations and recovery counterexamples must
pass before this area joins the thirteen completed Phone source/host
compositions. Device acceptance and a complete Android client build remain
unverified. Historical v17 contracts and earlier component results are retained.

## Passive native source v5

`phone-snapshot-observe` accepts exactly `schemaVersion:1`, a fresh 32-character
hexadecimal `commandId`, `action`, and the 32-character hexadecimal `runId`.
There are no capture, export, expected result, filename or state inputs.
Version 2 added the source-bound original native review observation (review
component contract v1). Review absence is distinct from a missing window,
ambiguous original component or an unqualified similarly named item. Hidden
reviews remain observable during capture. Capturing/processing, actual images,
export ticket/busy state, upload path, format and mode are read from the real
component; they are never inferred from delivered input. The current capture
inventory and its history are copied under the same native capture lock.
The existing candidate/process-bound private source transport writes
`phone-snapshot-observation.json`; observations require an existing session.
The source has its own request nonce, native instance/sequence, process ID,
request and capture timestamps. It must arrive within five host seconds and
remain fresh within the existing 1.5-second product-evidence window.

`PhoneSnapshotHistory` records original native capture insertion, existing
capture/upload signals, and actual upload insertion. Every row retains its
original wall-clock and monotonic timestamp. A separate read returns the actual
`Snapshot::_captures` objects' IDs/states/announcement flags and the currently
retained uploader objects' paths. History overflow (256 events), invalid events
or clock regression permanently mark that native history incomplete. There is
no reset operation and no replacement of a missing observation by empty state.
Successive reads require the same native/history instances and the unchanged
full event prefix. Original paths remain in private source files and must never
be copied to public result JSON. Public resources need opaque owned labels.

Version 5 adds the original VM-bound script capture history described below.
Version 3 added the original Android export source. Version 4 requires export
component contract v2. The real Java adapter records its actual native handle,
ticket, Activity generation, original validated source path, original document
or MediaStore URI and callback values. Each request has a new opaque identity.
Insertion, completed copy, successful publication, actual deletion return
count, chooser selection, deferred result and native delivery are distinct
events. A read observes a deep copy under the recorder's lock; it cannot mutate
or reset any callback history. The bound is 256 original events; overflow,
unknown values, foreign/overlapping responsibility or clock regression leave
the source permanently incomplete. Source replays require the exact immutable
prefix. URI and source-path originals stay in the private evidence file.

Export v2 retains separate original IO submission, executor acceptance/rejection,
worker entry and worker exit events. Each actual worker has a new opaque ID
under its original native export request. `pendingIo` is independently checked
against that complete immutable history. Cancelling/closing the native lease
does not hide still queued or running file work; cleanup requires both the
closed original lease and an empty original IO inventory. Worker exit is recorded
only after the actual copy/MediaStore function's existing `finally` block,
including its real cancellation deletion. A fast worker may finish before the
executor call's acceptance is recorded; that original ordering is retained.
No expected IO count or result is accepted from the caller. Missing starts,
foreign/duplicate completions and hidden outstanding work cannot qualify quiet
state. Older v3/v1 sources fail the version gate rather than supplying assumed
empty IO inventories. Ordinary builds still execute the original Runnable
directly, without the E2E recording wrapper.

The capture/review hooks require `OVERTE_E2E_FEATURE_TESTS`,
`ANDROID_APP_PHONE_INTERFACE`, `--testScript`, and the existing native test
lifecycle gate. The Java export recorder is instantiated only when its native
gate confirms that same Phone build and test-script process. The shared Java
source does not enable recording in other Android clients or ordinary builds.
The native read-only export method returns empty outside that gate or before a
real backend has initialized; an absent backend never becomes observed absence.
Capture, upload and export behavior is unchanged. In particular, a chosen
component and even the existing product `success` callback do not prove
successful system saving or receiver consumption. The callback contract itself
supplies no destination bytes or receiver acknowledgement. The separately
versioned readback component below must qualify an actual saved destination;
sharing still needs its external receiver.

## Original Save readback component v1

`phone-snapshot-readback` accepts exactly `schemaVersion:1`, `commandId`,
`action`, `runId`, `operation`, `exportRequest` and `resourceId`. Operation
`observe` takes empty request/resource fields; `read` takes an original export
request identity and a new opaque read-job ID. Repeating the same job ID is
idempotent and returns that original acquisition; it does not refresh its time.
A fresh acquisition needs a new retained job ID. Cancellation and copy removal
take an owned job/copy ID; `retire-copies` takes empty fields. Read-only product
transport allows observation/read only. Cleanup needs the normal guarded
mutable transport. No caller URI, capture path, expected hash, expected size or
requested product outcome is accepted.

The real Java Save path registers only its original ContentResolver and actual
MediaStore-insertion/document-return URI. Reads are admitted only after actual
copy completion (document) or successful publication (MediaStore). A separate
worker opens that URI again in read mode and consumes the provider's actual
stream. It never reopens the private capture path to manufacture Save evidence.
The original request, job and new private copy identities remain distinct.
Jobs are queued/reading/complete/failed; acceptance alone supplies no file.
Only successful consumption and original descriptor closure can complete a job.
The source records original job times, measured byte count/SHA-256 and the
private copy path. It has an immutable instance, increasing observation sequence
and actual wall/monotonic clocks. Blocking provider acquisition uses Android
CancellationSignal plus a 15-second watchdog that closes an opened stream.
The source is never represented as initialized empty state before creation.

The 64-job/copy bound and 256-MiB original-byte ceiling are enforced. Copies live
in a new process-owned `files/overte-snapshot-e2e-<nonce>/` directory (0700), each
in a newly created private file (0600). File/directory identities, aliases and
permissions are checked independently. Completed-copy removal additionally
requires unchanged actual bytes. Failed/partial acquisitions retain owned
cleanup responsibilities. Unknown files, pending original closes, replacement
paths and incomplete worker retirement remain failures. Repeated cleanup
revalidates actual absence, including after copy-directory retirement.

Copy retirement says nothing about deletion of the actual OS destination. That
separate URI cleanup, normal review/system-sheet input, receiver consumption
and public ownership are composed by the current v18 facade below. Bounded
binary acquisition below retains the completed Save readback in private host
artifacts. This component alone cannot qualify the extended Snapshot capability
or a complete feature/cleanup result.

## Composition requirements

The facade uses normal review inputs and retains actual pending/cancelled UI
observations (including cancellation before native capture allocation), with
immutable process/run ownership. It joins native capture IDs with
the actual unique capture filename, original bytes and a fresh fixture marker.
Do not infer capture completion from a button click or filename existence.

Android Save is `media-store` on API 29+ and `document-picker` on earlier
supported APIs; these require `savePermission:not-required`. Use the common
backend profile: do not simulate iOS Photos permission denial on Android.
Join the retained original Android request/URI identity to actual destination byte readback,
chooser cancellation and an explicitly owned receiver's independently read
consumed bytes. A chosen component ACK is insufficient. Upload failure/recovery
needs the controlled account service and independently retained multipart bytes
plus native completion. The facade uses the normal Upload input; independent
HTTP provider originals prove its effects.

Cleanup must cancel outstanding capture/encode/upload/system requests, prove
native and Android quietness, restore original review settings, remove only
the exact original owned files/destinations, terminate the actor and retire all
private journals with retained original proofs. Lost replies or partial cleanup
must preserve intent and remain red until those responsibilities are verified.

## Host checks

`test_snapshot_source.py` exercises real source-reader logic with synthetic IO,
including ignored/missing inputs, stale/foreign/changed histories, invented
responsibilities, foreign paths, candidate changes and deadlines.
`test_snapshot_native_history.py` compiles the real recorder with prepared Qt6
and exercises actual clocks, disabled instrumentation, immutable returned
copies, overflow and unknown phases. It does not compile `Snapshot.cpp`, its
renderer/upload dependencies, or the Android APK. These checks establish test
logic and recorder contracts only; they establish no device acceptance.
`test_snapshot_native_review.py` additionally compiles the real passive review
reader and loads unchanged product QML with a synthetic Snapshot script service
and the actual desktop unavailable-export backend. It checks real pending and
cancelled message handling, hidden reviews, qualified absence and rejection of
foreign or duplicated components. It proves no Android saving or sharing.

`test_snapshot_export_originals.py` compiles the actual passive Java recorder
and checks immutable callback identity, original clocks, concurrent snapshots,
foreign callbacks, late success after retirement, missing consumption proof,
overlap and permanent overflow. `phone-snapshot-export-native-test.py` compiles
and links the actual `NativeSnapshotAdapter.cpp`, its generated Qt metaobject
and the original `SnapshotStorage.h` against prepared host Qt6 and JDK JNI
headers. Six runtime checks cover Phone, other-Android and ordinary build gates
with and without `--testScript`, plus the unavailable-backend boundary. No JNI,
storage or registry implementation is replaced by a synthetic seam. This host
build establishes neither Qt5/Android ABI compatibility nor a complete client
build. The actual Snapshot Java sources also compile with the prepared Android
34 SDK and AndroidX Core; neither that compile nor the host contracts execute
MediaStore, a document provider, a chooser or a physical device.

`test_snapshot_readback_source.py` checks original packet identity, missing or
foreign output, old replies, source replacement, terminal-job rewrite and the
read-only cleanup boundary. `test_snapshot_readback_jobs.py` executes the real
Java worker/files/clocks using explicit synthetic Android provider/descriptor
boundaries; cancellation of an actual blocking host provider, descriptor-close
failure, idempotent job IDs, fresh reacquisition and worker retirement are
exercised. Original Java observations are also passed to the strict Python
validator, changing only the permitted private-root boundary for host files.
`SnapshotReadbackFilesHostTest` covers actual stream/filesystem failures and
preservation of foreign files. `phone-snapshot-readback-contract-test.py`
compiles the original TestScriptingInterface command function against real Qt
JSON/thread APIs with explicit synthetic lifecycle/JNI endpoints; those endpoints
return only an ACK. It does not compile the complete scripting translation unit.

## Original Save binary acquisition v1

`PhoneSnapshotSavedFiles.acquire(copyId)` composes the existing candidate-bound
`AndroidSnapshotFiles` binary transport and private artifact publisher with
`PhoneSnapshotReadbacks`. It accepts only an opaque original completed copy ID;
callers cannot select a URI, path, expected bytes, digest or successful result.
Fresh native observations before and after transfer must retain the same
process, native/Java instances, completed job, original file and original job
time. A repeated acquisition never refreshes that original completion time.
The existing 1.5-second evidence window applies across the transfer.

Fixed run-as scripts allow only the app-private owned readback directory/file,
check actual directory/file modes (0700/0600), reject symlinks and hardlinks, and
retain actual device/inode/size/hash metadata. Bounded binary header/footer and
SHA-256/size checks detect missing or changed output; a second OS metadata read
and native observation detect replacement, changed ownership or retirement.
The source's real Java observation also independently rechecks its retained
file/directory identities. Only measured original bytes reach the inherited
private, content-addressed artifact publisher. URI and native path never enter
the returned artifact metadata.

`test_snapshot_saved_files.py` executes these actual fixed shell scripts against
a private host filesystem through an explicitly synthetic SDK boundary. Nine
cases include binary NUL/non-ASCII bytes, ignored/foreign IDs, stale or missing
readback jobs, source replacement, changed bytes, same-byte inode replacement,
file aliases, permissions, truncated transfer and foreign host artifacts.
These host checks do not execute run-as on Android or prove OS saving, receiver
consumption, complete cleanup, product function or device acceptance.

## Original script capture history v1

Outer Snapshot source v5 requires a separate immutable, bounded (256-event)
`PhoneSnapshotScriptHistory`. It records actual `pending`, `processing`,
`complete`, `cancelled` and `error` calls from the unchanged normal Snapshot
workflow. Pending is recorded after actual timer registration; cancellation is
recorded after actual timer clearing and the cancelled review message. Unknown
or retired callback request IDs return before recording. An idle Cancel records
nothing. No input, expected phase, supplied caller identity or reset is exposed.
Missing/foreign VM provenance, overflow and clock regression permanently leave
this component incomplete; older sources fail the v5 gate.

The actual V8-to-QObject dispatch obtains the nearest actual V8 Script ID. Its
native call scope retains the real manager membership, submitted source and
compiled included-code origin. Only the narrow `featureCaptureEvent` observer
method additionally copies the selected original function source's actual Qt
timers and retained registration/callback activity on the manager thread. It
never evaluates JavaScript, observes a foreign heap, clears a timer or alters a
capture delay. Every event keeps its original request/mode/review revision,
wall/monotonic clocks and complete original caller/work metadata. The strict
reader rejects missing contexts, foreign sources, repeated/late terminal phases,
rewritten prefixes, impossible work/timer facts and native instance replacement.
The public owner still must join the reviewed Snapshot code pin, the actual
review and independent fresh work/files before deriving a product checkpoint.

`test_snapshot_script_native.py` compiles the actual recorder header and unchanged
extracted Snapshot observer, ScriptManager call-scope and timer-reader function
bodies with real prepared Qt6. Its VM manager/source boundary is explicitly
synthetic; real Qt timers exercise registration/removal while foreign timers
remain untouched. Disabled, missing/foreign/uncompiled/wrong-thread caller and
permanent overflow cases stay red. This does not compile V8 or the complete
Snapshot/ScriptManager translation units. `test_snapshot_script_history.py`
checks the strict Python join and native packet boundary. The original
`snapshot.production.test.js` additionally checks real script event/timer
ordering, ignored idle Cancel, foreign/retired completions and the unchanged
desktop path with an explicit native observer seam. The current normal Qt
FastCancel, facade and cleanup composition have separate source/host checks
documented below; these component results alone do not qualify devices.

## Normal original Qt controls v1

`phone-snapshot-ui` uses the existing `NormalControlUi` source-token/input
mechanism (Phone surface 10). Qualified original Snapshot review controls cover
name, real mode/format choices, Capture, Cancel capture/upload/system request,
scrolling and the exact original image row's Save/Share/Upload buttons. Dynamic
export IDs are SHA-256 labels of actual privately observed image paths; neither
a desired path nor requested success can select an unrelated row. The page must
come from the original native review QML context. Duplicate controls, replaced
objects, stale/consumed tokens and foreign overlays fail closed. Ordinary mouse,
focused field and keyboard choice events enter the actual rendered Qt window;
no script handler, property setter or export API supplies an input shortcut.

`PhoneSnapshotIO` reuses `PhoneScriptFileIO`'s candidate/process-bound private
probe transport, five-second exchange budget and 1.5-second source freshness.
It retains original native packet metadata and requires durable intent before
input delivery. Read-only actor transport permits observation only. A delivered
input never creates capture/file/export evidence; the extended owner must obtain
those independently from original producers. The public Snapshot triple is now present behind its default-off full-profile
gates; these control tests alone do not qualify that composition.

`test_snapshot_native_controls.py` compiles the unchanged normal-control helper
and actual field-input implementation with real Qt6. It loads unchanged product
review/Android-backend QML with explicit script/OS service seams, then checks
real name/choice/capture/cancel/Save/Share events and actual original image-row
arguments. Its actual Qt observation is additionally checked by the strict Python
reader; only the transport envelope's command nonce/action are supplied at that
explicit boundary. Foreign/duplicate components, replaced tokens, consumed input
and a real obstructing overlay remain red. The four native cases pass; the
47-case selected source/transport/native composition passes. These tests prove
no Android backend, successful OS export, fast pre-render cancel or device
acceptance. `test_snapshot_controls.py` separately checks missing/stale/foreign
packets, ACK-only inputs, exact paths, closed Probe grammar and read-only refusal.


## Bounded normal Capture/Cancel recipe v1

`phone-snapshot-cancel` accepts only schemaVersion 1, commandId, action, runId,
jobId, operation and request. IDs are opaque 32-character hex values. Start
carries the existing exact normal Snapshot Capture activation, whose commandId
must equal jobId. Observe/retire require an empty request. Neither expected
state, caller delay, path, timer ID nor script handler is accepted. The existing
native launch/lifecycle/candidate/PID gates apply. Read-only actors can observe
only; they cannot start or retire a job. Up to eight original jobs are retained
without resetting or replacing history. Repeating the same start returns the
original job and never replays input. A foreign run/input cannot borrow a job.

The target recipe uses the same physical Qt mouse events as normal controls.
After actual Capture delivery, a precise two-millisecond local observer waits
for an actual new VM-bound animated pending event, both original active
single-shot timers (350 and 60000 milliseconds), capturing review, unchanged
normal input context and unchanged native capture history. It then delivers
the actual normal Cancel control before a conservative 300-millisecond bound.
The existing product delays and event loop remain unchanged. Missing/ignored
input, stale or foreign events, replaced history, timer expiry and native
render submission fail the original job. No handler, native cancel function,
timer removal or alternate capture implementation supplies these inputs.

Completion retains original before/pending/cancelled native-core and review
copies, actual input receipts, original event times, unchanged native history,
matching cancelled script context and observed empty original timer map.
Historical sources use their actual native-core v1 schema; they are not relabeled
as an outer Snapshot-v5 observation with invented Java/export fields. Each
transport response independently includes native instance/sequence/PID, fresh
request/capture times, current original source and the complete bounded job
inventory. The Python reader enforces the five-second operation deadline,
1.5-second freshness window, immutable original prefixes and same-run identities.
It retains historical times instead of refreshing them at acquisition.

Retirement stops no product work and deletes no product files. It requires a
terminal recipe, inactive local timer and a new original idle observation.
The first retirement original remains immutable. Repeated retirement checks
current state again; late actual work refuses retirement and remains visible.
A completed recipe supplies no whole Snapshot verdict: the public owner still
needs reviewed compiled-source pins, independent fresh native/UI/file/peer
observations and the existing three-second no-late-results window.

Host checks compile the unchanged Test.phoneSnapshotCancel method and the
actual helper, normal QML, physical Qt input, clocks and timers. Explicit
DependencyManager/lifecycle/OffscreenUi and VM/script producer seams remain;
these are not a complete TestScriptingInterface translation-unit, Android
runtime, product rendering or device acceptance check.


## Normal review input composition v1

`PhoneSnapshotControls` uses the existing candidate/PID-bound `PhoneSnapshotIO`
and normal SDK tablet controls. It records SDK intent before input, opens the
actual SNAP entry, checks fresh original name/choice transitions and selects
Save/Share/Upload by the exact current original image path's hashed control ID.
An acknowledgment never supplies a file, save, receiver or HTTP result. Missing
or ignored transitions, foreign paths and failed durable intent remain red;
uncertain mutations are never automatically replayed. Reads and scroll steps
are bounded and use fresh original controls each time.

`PhoneSnapshotIO.plan_capture` persists the exact next normal Capture command
without delivering it. The bounded native Cancel recipe can consume that
original command once; the source command's nonce/token/generation/sequence
and durable intent remain distinct from actual pending/cancelled observations.
A plan is rejected for a non-animated normal choice. These controls still do not
advertise the public Snapshot feature triple or retire OS results.

The v18 extended Snapshot suite retains the original controlled domain rather
than replacing it with a serverless scene. Normal upload requires the actual
non-null connected domain identity and ordinary owned-account login. The
standalone snapshot-output-parity foundation keeps its original scene profile;
only the extended feature suite adds the explicit domain-enter prerequisite.
Missing navigation.enter-domain must fail the mandatory capability gate before
any device discovery or feature input. A successful input acknowledgement does
not establish domain connection, account authentication or upload success.

`PhoneSnapshotMeasurements` acquires original configured Script roots, original
ScriptManager inventory, original Snapshot history and a second original root
read in that order. All four packets must belong to the same native instance
and PID and fit the existing 1.5-second freshness interval, including an
independent monotonic acquisition budget. The unique assigned, running
`system/snapshot.js` manager must have submitted and actually compiled the
reviewed UTF-16 source from the existing fixed admission catalog. Every
retained capture/cancel VM caller must match that original manager, code and
compilation exactly. Historical event timestamps remain unchanged. The join
produces source provenance, not a capture, cancellation, export or cleanup
verdict. Those still require normal input, original lifetimes/files/pixels and
separate actor facts. Counterprobes substitute consistent foreign code, caller
compilations, manager identities, pending duplicate managers and old/out-of-order
reads; matching filenames or fresh request IDs cannot qualify those sources.

`PhoneSnapshotPlatform` reads the selected bound target's original Android SDK
property through the existing ADB transport, with candidate/process guards on
both sides and a 1.5-second wall/monotonic budget. It uses the same API-29
branch as the actual SnapshotAdapter: MediaStore at API 29+, the ordinary
document picker below it, and no Photos permission on Android. Missing or
changed properties fail closed; configuration cannot supply a measured SDK or
Save backend. The property establishes platform selection only. Actual Save
requires the separately retained original provider bytes and OS destination.
The Appium composition factories now expose the original platform/VM readers
and the normal SDK-tablet/Qt Snapshot controls. No public feature capability
is enabled by these internal factories.

`PhoneSnapshotSystemUI` provides ordinary SDK selection/Back for the original
resolved Android share chooser and the separately pinned consuming Activity.
Its owning composition must supply the original OS component resolution and
an explicit candidate/kernel/session guard for this one handoff; existing
foreground-only native command guards are unchanged. Each read brackets a
bounded actual accessibility tree with actual package/Activity queries and
checks both wall and monotonic freshness. Selection requires one displayed,
enabled fixture label inside its actual clickable original bounds, a private
durable input intent and a fresh identical tree before one ordinary W3C touch.
Back similarly records intent before one ordinary SDK action. Ignored input,
changed windows, duplicate or disabled labels and slow intent writes stay red.
A returned UI transition never proves receiver consumption. The facade must
separately acquire the receiver's actual original bytes/URI/UID/close evidence,
then return normally from that owned Activity before further native reads.
This internal component does not by itself enable the public Snapshot triple.

The original chooser resolution reader queries the selected target's real
PackageManager for ACTION_CHOOSER, reads the exact resolved package UID, and
resolves again within the existing 1.5-second wall/monotonic budget. Both the
framework `android` chooser and separate resolver-package layout are admitted
from original OS results. It launches nothing. Its result must additionally
match the actual native Intent's independently recorded chooser component and
UID; the preflight OS query alone proves neither actual routing nor a grant.
Missing/ambiguous results, a changed resolver, a foreign UID and a stale or
slow query cannot default to a configured chooser. Actual Android PackageManager
execution remains untested; host tests exercise explicit OS transport seams.

`SnapshotSystemContext` reuses the existing original OS/kernel/session lifecycle
observer across that explicit share handoff. It requires a durable live owner's
authority on both sides, the unchanged installed candidate, target, original
SDK session/generation and kernel process; it brackets the actual current
package/Activity with two matching original lifecycle reads. Only the original
resolved chooser, owned consuming Activity and a genuinely foreground original
app are admitted. A hidden foreign Activity, stopped process, changed SDK
session or missing owner authority stays red. The dedicated Appium factories
create no session, install nothing and send no native in-client command while
a system surface is active. The normal app foreground-only native writer and
observers are unchanged. Separate receiver consumption uses the same narrow
context plus its existing fresh independent APK/UID/kernel/file identity checks.

The capture-facts reducer retains the original baseline and joins subsequent
VM contexts with actual native allocation/terminal events. A VM `complete`
without its original native begin, final path and completed status is rejected,
as are foreign contexts, source-manager/root changes and retained live work.
Pending/cancelled history is raw provenance only: the complete owner must also
require the independently retained normal fast-cancel recipe, and a native
complete path still needs original file identity, encoded bytes and pixels.
The reducer never converts an acknowledged input or an empty result into a
file, cancellation or completed capture verdict.


The separate native Snapshot settings lease v1 captures only the original fixed
13 Snapshot keys plus the actual native `Setting::Handle<QString>` format cache.
Capture, restore and retirement require actual review absence, no native capture
or upload and no pending/processing original script context. Commands cannot
provide settings, desired values, paths, or a claimed UI-closed state. A restore
names a durable operation ID and the SHA-256 of a freshly observed original
typed Qt serialization. The native owner retains the original typed values and
presence. It performs an atomic compare/restore of only those keys, restores the
real native Handle through its normal set/remove path, then restores exact raw
presence/type after any legitimate Handle normalization. Both independent
readbacks must match the original; a raw-only restore cannot pass. No production
Handle or general script settings API changes.

Interrupted restoration retains its immutable operation ID, expected digest and
native basis. Resume accepts only the original, basis or precisely known partial
cache/raw transition; changed foreign values or a replacement operation stay red.
The native handback timestamp is measured after the successful original reread,
retirement cannot revive a scope, and another scope cannot replace a live owner.
Private typed originals remain private. The host reader checks original PID,
nonce, monotonic sequence, original digest, typed serialized bytes, closure and
actual handback continuity. Read-only actors may observe only. Freshness remains
1.5 seconds and transport polling remains bounded at five seconds.

The dedicated host compiler check compiles actual SettingManager.cpp plus MOC,
the unchanged Handle template and Setting::Interface member bodies, and the
unchanged Snapshot cleanup and Test gateway bodies. Dependency/bootstrap and the
surrounding GUI/VM are explicit host seams; only unused GLM declarations are
replaced for this partial host build. Actual Qt raw/cache restoration, original
presence/type, ignored-cache counterexample, foreign-key refusal and interrupted
CAS recovery pass. This does not compile the complete Android product or prove
native GUI closure/device behavior. No public Snapshot capability follows from
this prerequisite alone.


The existing five-format `snapshot-output-parity` flow has an original ownership
composition for the complete-feature profile. `OVERTE_PHONE_FEATURE_SNAPSHOTS=1`
selects it inside the existing normal Snapshot operations. The full public
triple additionally requires this ownership composition and its other gates. The standalone legacy format decoder
profile retains its narrower existing scope. Complete-feature preparation must
require the owned foundation and cannot substitute the legacy profile.

The foundation persists a fresh explicit 32-hex scope before native or ordinary
input, captures the actual native settings lease before opening SNAP, and plans
each original `parity-<nonce>-<mode>` namespace before normal Capture. All five
formats use the existing PhoneSnapshot flow. No extended run adopts this scope.
A pending descriptor/capture can project no *qualified completed* output set to
the existing bounded decoder poll, while its actual original files and partial
rows remain durable cleanup obligations. Preflight still requires the actual
namespace to be empty. Failed, foreign, missing or changed originals never use
this pending projection; extended file acquire remains strict.

Normal Close first requires an independent three-second original no-work window,
then retires all native/host capture files, restores and retires the typed native
settings lease, and verifies another original three-second quiet window. It
then removes both private ownership journals after fresh native/OS absence,
sealed-prefix, original instance and host-file checks. An uncertain journal
unlink resumes from retained archival intent and original source identities.
Lost target delete replies reuse the same durable operation; ignored input,
unfinished capture, missing settings restore, same-byte foreign inodes, changed
candidate/process/root, or late original activity keep closure red. Existing
adapter cleanup also recovers a retained foundation even after the activation
flag is removed, before normal shared process teardown. Stable source-lock files
retain their existing shared lock-domain behavior.

The dedicated composition checks execute real private filesystem scripts,
original inodes/bytes, journal CAS, target/host unlink and recovery with explicit
native/UI producers and simulated clocks. The existing normal W3C five-format
and byte-decoder tests remain separate checks of their documented boundary.
These simulations do not establish Android rendering, original OS behavior or
product/device acceptance. Public extended Snapshot composition remains open.


## Independently retained uploaded bytes

The readonly `/runs/<run>/snapshot-upload/original/<request>/<nonce>` route reads only the original successful, delivered image POST from the existing HTTPS Snapshot provider. It checks the original private body journal, device/inode, mode/link/owner and complete SHA-256 before parsing that actual retained multipart again. It returns that payload with original request/ticket/provider/body/image identity and a separate current acquisition epoch. Original upload completion is never retimed. Missing, modified, replaced, retired, failed or foreign requests cannot supply bytes. No native capture path or caller-provided body/hash is accepted.

`PhoneSnapshotUploadBytes` brackets binary acquisition with its own fresh provider reads using the existing role credential. It checks the fresh nonce and exact provider/run/request/ticket/domain/HTTPS-origin identities, original multipart receipt and payload metadata, actual decoded bytes, immutable completion time and real five-second acquisition/freshness guards. This separate binary route retains the existing 32 MiB original multipart ceiling and leaves the generic Client's 1 MiB JSON ceiling unchanged. The resulting file source is `snapshot-upload-original`; private capture bytes cannot be relabeled as upload evidence. Both actor and adapter reader credentials can acquire originals, while the product access token and mutation requests cannot use this route. This supplies component evidence only; the default-off public composition still requires both complete backend replays.

The dedicated host check uses real loopback TLS, actual multipart uploads, private original inodes and image decoding. It includes an original PNG larger than 1 MiB, changed wire bytes/inodes/permissions/links, missing/retired sources, foreign roles/run/request/ticket/nonces, stale metadata, changed payload and an advanced five-second acquisition clock. SDK/native request producers remain explicit synthetic seams; no live product upload or device acceptance is claimed.
### Passive original source during ordinary OS handoff (version 1)

The primary starts `phone-snapshot-handoff` while the original Phone process
and normal foreground command guard still hold. Its closed command contains
only schemaVersion, commandId, action, runId, handoffId and operation
(start/observe/retire). No caller duration, expected state, source, URI or OS
component is accepted. One active owner and eight retained owners per native
process are allowed. A real 250 ms Qt timer acquires the original sources;
60 seconds is an immutable measured lease, never a renewable timeout.
Retirement actually stops the timer and takes a final original sample. An
expired or failed owner remains failed even after its resources are stopped.

The atomic private `phone-snapshot-handoff.json` contains source version 1,
the original Test instance/PID, publication time, original source and the
complete bounded original job summaries. The source contains its own immutable
instance/run/handoff/PID/start/deadline, actual sequence/time, complete/error,
retired/timerActive/readActive and this exact original batch:
`context`, `group`, `readbacks`, `captureFiles`, `upload`. Context version 1
reads original lifecycle counters and AccountManager passive observations on
their actual owner thread. The existing pinned roots/script/Snapshot/roots
join, native readbacks, capture-file FD inventory and upload lifecycle getters
are called directly. No JavaScript handler or UI mutation is used. Original
VM event times and native/file completion times are preserved.

The SDK independently binds the actual foreground start result, then reads
only this private file under the existing narrow OS/kernel/session handoff
authority. Actors cannot start or retire it. They send no background client
command. Every nested original grammar, fixed compiled script pin, actual
PID/instance/run, source order, closed fields, account history and monotonically
retained native histories are checked. Sources remain limited to 1.5 seconds
freshness, five seconds polling and the original 60 second deadline. An old
file with a new host read/publication time, missing getter, ignored command,
foreign evidence, changed source, missing retirement or stalled Qt event loop
fails. The host never relabels a cached pending frame as current. Normal
foreground-only command protection is unchanged.

`test_snapshot_handoff.py` exercises synthetic native/VM/OS boundaries and
negative histories. `test_snapshot_handoff_native.py` compiles the actual timer
helper and unchanged native gateway body against explicit original-getter,
account and lifecycle seams, writes a real private atomic file, and waits the
actual 60 second deadline. The full native product translation unit, Android
background event delivery, OS UI and physical client remain unverified.


### SDK26–28 ordinary document picker and independent reader

`SnapshotDocumentResolution` reads PackageManager resolution twice around the
actual resolved package UID for precisely CREATE_DOCUMENT, OPENABLE and
image/png. Its version-1 document-resolution contract is separate from the
share-chooser contract. The original kernel/candidate/session handoff checks
admit only that actual resolved activity and the original Phone foreground
window; a share receiver or another activity in the same package is refused.
No in-client foreground command protection is weakened.

`PhoneSnapshotDocumentsUI` uses normal W3C touch/Back. It reads and brackets the
actual OS package/activity/XML, opens the normal root drawer when necessary,
selects the unique displayed **Overte Snapshot Evidence** root and observes its
actual toolbar title. Save requires the unchanged actual native PNG basename
in the unique displayed filename editor and the enabled Save control. Every
input first records durable intent and then rechecks the identical original
window/tree within 1.5 seconds. Changed, duplicate, disabled, missing or foreign
controls prevent input. Ignored Save/Cancel/selection ACKs cannot qualify a
transition and are not replayed. UI transitions supply no saved-file verdict.
The English navigation descriptions are part of the controlled English test
UI prerequisite; unknown OEM layouts fail rather than select another provider.

`PhoneSnapshotDocuments` reads the separate fixture's exact original JSON and
binary routes described in [DOCUMENTS.md](../../fixture/android-snapshot-receiver/DOCUMENTS.md).
Its original APK/UID/PID/kernel identity, native provider instance and exact
private root identity are bound by the primary and independently attached by
the readonly actor. New nonce/sequence/current source times, all creation
plans/documents/actual FD closes, historical identities and original completion
times are retained. Reserved descriptor observations may be polled for at most
five seconds; a permanent incomplete source remains red. No caller-provided
content, path, writer identity or desired result is sent to the fixture.

Binary acquisition joins the native immutable SAF identity to the independent
provider source, actual resolved picker creator UID and separately measured
Phone writer UID, then reads the actual original bytes, verifies full size/SHA
and decodes the PNG. Fresh independent observations before and after acquisition
must retain the same original document and actual closed FDs. Completion time
stays historical; acquisition time is separately observed. Wrong writer/creator,
borrowed native identity, changed process/root/inode, stale/replayed source,
missing/non-PNG bytes and a five-second overrun fail. Provider retirement can
only remove its independently empty original root after normal native one-send
DocumentsContract deletion has already proved every destination absent. Actual
FDs, source transfer workers and callback thread must be retired. ACKs and an
empty filtered document list cannot establish cleanup.

Factories `_snapshot_document_resolution`, `_snapshot_document_ui`,
`_snapshot_documents` and `_snapshot_phone_uid` expose these narrow prerequisites.
They neither install the fixture nor launch a document Intent directly. SDK
transport/PackageManager/OS-window producers remain explicit host-test seams;
the Java fixture/native ownership has its separate actual-file/API34 compiler
checks. Android DocumentsUI/Binder/URI grants and physical acceptance remain
unverified. This component alone does not advertise complete Snapshot support.
### Current acquisition of a retained export original

The extended owner uses `PhoneSnapshotSavedFiles.acquire_current(copyId)` and
`PhoneSnapshotConsumer.acquire_current(grant, capture)`. Both acquire the actual
retained bytes again through fresh original owner observations. They retain the
unchanged `originalCompletedEpochMs` and report the actual new acquisition as
`capturedEpochMs`; an old completion is never rewritten as a new completion.
Save still requires the same completed job and private copy before and after
transfer, exact device/inode, mode, link count, bytes and SHA-256. The consumer
still requires its distinct original UID/process, URI/grant and closed copy.
The complete acquisition has a real five-second deadline. Stale current source,
changed bytes/inodes, lost guards and slow acquisition remain failures. The
existing `acquire()` foundation behavior and decoder are unchanged. These are
host/source boundaries, not physical Android acceptance.

### Public-state measurement joins

`overte_phone_snapshots_measurements` derives public fields from the role's
original VM/native group, owned FD/file inventory, Android export callbacks,
actual OS destinations/readback jobs, separate receiver identity and copy, and
actual HTTPS multipart/reply receipts. It accepts no expected state or desired
count. A retained effect is rejoined against its current actual owner. Save
requires actual copy/publication and closed readback; Share requires the actual
chosen component, URI/UID/grant and closed independent consumer copy; Upload
requires both original HTTP exchanges and terminated native lifetimes.

Before this scope issues any export, the exact uninitialized readback packet
remains explicitly unavailable. An unchanged empty original export prefix can
establish that no scope-owned export has occurred; it cannot establish an empty
OS destination inventory or qualify cleanup. After export, complete fresh v2
readbacks are mandatory. Empty live `captureHistory` requires actual scope
retirement: sealed and absent files, original typed settings restoration, fresh
OS absence, revoked grants, terminated Java/native work and the separate
consumer's actual retirement. Immutable raw VM/native histories are retained.
The facade must additionally establish its independent real quiet windows,
host-owner retirement and actual actor exit.

The dedicated host counterexamples cover actual file identities, unfinished
inventories, borrowed Save/Share receipts, missing OS publication/consumption,
changed bodies/providers/tickets/replies, old current sources, and cleanup that
leaves settings, descriptors, workers, grants or files live. The upload join
uses the real loopback HTTPS provider's retained multipart original. Native,
VM and Android producers in this check are explicit synthetic seams; this
component does not enable or qualify the complete public Snapshot capability.

### Readonly original file inventory across an owned OS handoff

`_snapshot_system_files(..., handoff_source)` combines the existing narrow
`SnapshotSystemContext`, the role's existing `PhoneSnapshotHandoff` reader, and
the unchanged private file transport/owner. `SnapshotSystemFileSource` accepts
only `observe` for that original handoff run. It sends no native commands and
cannot plan, delete or seal files. Every read uses a newly acquired passive
batch; the same role reader retains all its original nested sequence floors.
An independent readonly file journal attaches only to the original writer's
actual binding and still scans real namespace/root/device/inode/hash identities.
The primary writer and each readonly observer keep separate host journals and
copies. `_snapshot_system_platform` reads the actual SDK property under the same
narrow OS guard. Normal foreground command guards are unchanged.

The host check joins this passive source to actual private files and the existing
fixed shell transport. Mutation/foreign-run attempts, stale or foreign native
frames, rolled-back plans and same-byte inode replacement remain red. The native
passive producer and OS transport are explicit synthetic seams; no device or
background event-loop acceptance follows from this check.

### Independent DocumentsProvider joins in each role

The public-state input retains `documents`, `documentsBinding`, `phoneUid` and
`documentResolution`, together with its role's immutable
`snapshot-document-original` binary receipt. On SDK26–28, a saved count requires
both the original native Save/readback copy and the separate provider's actual
creator UID, measured Phone writer UID, original FD closure, bytes and inode.
Cleanup additionally joins the native destination's real deletion/absence to
the same provider's fresh retired root, original deleted document and terminated
FD lifetimes. Missing either original remains red. SDK29+ retains its separate
MediaStore branch.

`_snapshot_system_documents(..., binding=originalBinding)` permits only readonly
DUMP observation of that already bound provider under the current original
Share or Documents system context. It never masquerades the Share resolution as
a document resolution, and cannot arm or retire anything. The original document
resolution is retained independently for the actual creator-UID join. This
allows a role to recheck saved provenance while the later ordinary Share chooser
is foreground. The evidence namespace retains the separately acquired provider
bytes in addition to the actual native Save copy. The targeted SDK26 source
composition and retirement counterprobes remain synthetic Android/VM boundaries;
the complete common replay and physical acceptance are separate qualifications.


Closed Review FastCancel observations preserve the original recipe and both
append-only native/script histories. Start, before, pending and cancelled still
require the original visible Review and unchanged normal Capture/Cancel inputs.
Only observe/retire can supply `closedReadWorkRequestId`, the nonce of an already
completed original `feature-script-work-observe` owner-thread barrier. Native
code joins that nonce to its actual cached command/result, original manager,
submitted source and compilation; no caller-supplied work body is accepted.
Absent/hidden Review additionally requires actual current native idle state,
zero owned/unknown timers and callbacks, no evaluation, and original monotone
activity counters. Historical work timestamps are retained. Current source
loss, changed histories or unfinished work keep observation/retirement red;
retirement never cancels work or changes the original complete/failed result.
The Qt/QML contract runs the unchanged Test method and actual input/timer code
with explicitly synthetic VM/source producers; it is not device acceptance.


The separate `_snapshot_handoff_input` admits one previously planned normal
Save/Share button command while the original client is foreground. Its durable
issued intent precedes the only write to the existing fixed private command
file. After that write it uses the original narrow chooser/DocumentsUI system
scope and reads only the unchanged Qt input receipt. It never sends a client
command from OS context or changes the shared foreground-only writer. Missing
or uncertain receipts cannot replay a click, including after reconstruction.
The original prestarted passive handoff binding, fixed application identity,
original token/generation/sequence/path, five-second call deadline and native
lease deadline remain mandatory. Save/Share effects require independent current
file, destination or consuming-APK originals; the input receipt adds no effects.

Snapshot cleanup has two distinct original owners. Before fixture closure, the
normal animated Capture/FastCancel recipe must cause the actual owned story
DELETE and its current absence; native upload jobs, replies, file descriptors,
multipart bodies and callbacks must already be retired. The HTTPS fixture keeps
its immutable received image and multipart inode until the original Client
closes the run. Its unchanged `uploads` count may therefore remain one while
`stories` is zero. A retired live product scope may publish zero uploads only
after actual settings/file/OS/consumer retirement and fresh story absence; held
requests, missing DELETE or live native jobs still fail. After actual fixture
closure, strict finalization additionally requires the independent provider's
fresh `active=false`, zero uploads/stories/inflight, retired request rows and
its passive real body/sidecar absence checks. No retained raw history is erased
or relabeled to implement the live public projection.

Background recovery retains the original native lifecycle and durable input
stage. An observed background with no issued resume permits one ordinary
`app.launch`; a saved `resume-issued` stage only waits for the original
foreground return. Cleanup of an uncertain Home write already found in the
foreground archives the actual lifecycle without issuing Home or launch again.
Reconstruction requires the same actual process/session binding and the
original monotonic twenty-second bound. Expiry or a changed process preserves
the pending journal and fails. The host recovery counterprobes use actual
private journals and the original native packet reader with explicit synthetic
SDK/lifecycle producers; they do not qualify device execution or latency.

Handoff recovery counterprobes reconstruct the actual private owner and
immutable input archive with original handoff and input readers. A lost native
start result observes only the existing job; a durably issued Save/Share reads
only its original receipt. Missing jobs or receipts retain the pending journal.
A changed pending plan cannot acquire authority from the same run. A receipt
archived before the pending-clear write can be rechecked without admission or
another input. These native/UI producers are explicit transport seams; actual
OS-scope admission and independent Save/Share effects remain separate checks.

## Owned marker refresh v3

`background-resume` uses `refresh_marker()` on the existing active marker lease.
It never repeats `prepare`, creates a new run or replaces the fixture objects.
The closed private request has exactly `schemaVersion:1`, fresh hexadecimal
`commandId`, `action:"phone-create-fixture-input"`, `operation:"refresh"`,
`runId`, `fixtureInstance` and the new `ticket`. Run, instance, command ID and
ticket are 32 hexadecimal characters. The original fixture URL, extent and ROI
are retained from creation and cannot be supplied or changed by refresh.

The [native owner](../../native/PhoneCreateFixture.h) requires the exact active
run/instance and all three original local entity pointers. Under the same tree
write lock, missing/replaced/locked/parented/cloned entities or foreign children
refuse the operation. The existing Web marker's previous URL must still match
its original latest challenge. Normal `EntityTree::updateEntity` changes only
that marker's source URL and edit timestamp. Creation `originalInput`,
`createdEpochMs`, `originalView`, object IDs and retained ownership remain
unchanged. Release keeps its existing exact-owner and weak-lifetime checks.
The existing Phone E2E build, `--testScript`, candidate/process and GUI-thread
guards remain mandatory; this introduces no ordinary product operation.

Before any refresh, marker observation stays exact v2. After a successful edit,
the source sets `phoneCreateFixtureVersion:3` and adds
`refreshes:[{input,editedEpochMs}]` and `lastRefreshInput`. Native input receipts
retain `phoneCreateFixtureInputVersion:1`; the common contract remains v18.
The last input is exactly the last history entry; every prior entry remains an
unchanged prefix. Refresh history is bounded at 256, never evicted. Reused
creation/refresh tickets, old command IDs, changed same-command payloads and
refresh after release are rejected. Only the exact last command is natively
idempotent. A new distinct run after actual drainage starts at v2 again.

The host archives `markerRefreshInput` before its sole write and persists
`pending.kind="marker-refresh"`, the exact request and original archive index.
`markerRefreshDelivery` is only an input ACK. It then reads fresh original
inventory, requires the matching `lastRefreshInput`, original objects, actual
new URL and original edit time, and archives `markerRefreshOriginal` before
clearing pending. Lost replies and a crash before that clear recover by reading
the same original request's effect, including during cleanup; they never resend
the edit or create another fixture. Missing effects, changed intent/history or
a mismatching current object URL leave the journal unresolved. The existing
five-second source/call and freshness bounds apply. Release and full cleanup
must still drain the original fixture/Web resources.

The role selects its effective challenge from v3 `lastRefreshInput.ticket`
(v2 keeps `originalInput.ticket`). Readiness joins the actual URL getter and
edit timestamp, original geometry/view and a newly acquired current-ticket
world PNG. The earlier private capture keeps its own original capture ticket
and bytes. Neither the ACK, refresh history alone nor an older image proves
background/resume rendering.

The [prepared refresh checks](../../../../android/phone/tests/device/test_create_marker_refresh.py)
compile the actual E2E header with Qt6 and explicit tree endpoints, exercise 14
native refusal branches, and check reader prefixes, actual Probe grammar and
six durable facade recovery cases. The combined refresh/marker/native/facade
selection passed 51 cases in 29.488 seconds. The separate
[full retirement audit](../../../../android/phone/tests/device/test_snapshots_full_retirement_audit.py)
passed five cases in 90.218 seconds with actual TLS bodies, filesystem effects
and a separate actor process. These are targeted host/component results;
complete common SDK29+ and SDK26–28 replay qualification remains pending.

An already owned facade constructor establishes only immutable host-header
identity. Every `load()` selects actual foreground, background-recovery or
original OS-handoff authority again under the shared source lock, after checking
the fresh exact owner and immutable pending/handoff originals. A constructor
that waited while the primary opened or closed a chooser cannot retain a stale
foreground/system guard. Missing or foreign current OS context fails without
trying a foreground source. This selection neither delivers input nor retries
an uncertain action. Deterministic actual-journal counterprobes cover both
foreground-to-OS and OS-to-foreground transitions and unavailable OS authority.

## Current v18 public composition and configuration

The adapter's three public operations are `feature.snapshots.act`,
`feature.snapshots.observe` and `feature.snapshots.cleanup`. Their exact DTOs
come from the common [contract](../../feature_journeys/contract.py): all take
`contractVersion:18` and the original `runId`; act additionally takes
`fixtureUrl`, `ticket`, `verb` and `inputs`; observe takes `afterSequence`.
Unknown fields, wrong types, unowned URLs, arbitrary verbs and requested result
fields fail before delivery. Observe derives measured state and opaque resource
references from original sources. An act result of `performed:true` proves no
capture, Save, Share or Upload effect.

The explicit opt-in is `OVERTE_PHONE_FEATURE_SNAPSHOTS=1`; its default is zero.
Registration requires the existing bound controlled Phone debug candidate,
`OVERTE_PHONE_NORMAL_SNAPSHOT=1`, the owned account launch profile,
`OVERTE_PHONE_ACCOUNT_FIXTURE=1`, a separately credentialed adapter fixture
reader and an HTTPS fixture origin. It also requires the actual normal Snapshot,
foreground/process/launch, navigation, scene and probe capabilities. The common
catalog additionally enforces both `domain-enter` and `snapshot-output-parity`;
an unavailable mandatory capability stays red even in exploratory execution.
The legacy standalone decoder profile cannot substitute for the owned
five-format foundation.

The native E2E hooks require an explicitly prepared debug build. From
`android/phone`, use
`ORG_GRADLE_PROJECT_overteFeatureTests=ON ORG_GRADLE_PROJECT_overteVoiceTests=true ./build.sh build`
in the existing prepared build environment. The feature property defaults OFF,
accepts exact ON/OFF and leaves non-debug types OFF. Setting only the raw
`OVERTE_E2E_FEATURE_TESTS` environment variable does not activate Gradle
forwarding. See the [debug build contract](../../../../android/phone/docs/BUILD.md#dedicated-feature-e2e-debug-build).
This documents activation; a complete feature-enabled APK build remains
unverified.

`OVERTE_PHONE_SNAPSHOTS_CONFIGURATION` names the private configuration file. Its
closed schema is `snapshotsFeatureVersion:1`, `artifactRoot`, `imageExtent`,
`markerRoi`, `imagePolicy`, `fileImagePolicy`, `domainId` and
`receiverApkSha256`. Both image policies contain only `source`, `marker` and
`subject`; the source must be `world-render-target`. The actual marker and
subject rectangles must be bounded and disjoint, the domain must be a nonzero
UUID and the receiver digest must bind the actual separate consuming APK.
The artifact root uses the existing private ownership and inode checks.
Expected counts, expected hashes and credentials are not configuration fields.
Adapter access remains in `OVERTE_PHONE_FEATURE_FIXTURE_CONFIG`; the optional
`OVERTE_E2E_FEATURE_FIXTURE_URL` must match its original origin exactly.

The independent observer uses `featureObserverVersion:8`, `area:snapshots`,
`target`, `candidateArguments`, `fixtureUrl`, `actorToken` and bounded
`durationSeconds`. It builds its own credentialed Client and calls the actual
Snapshot actor's `step()`. All fourteen primary feature flags are explicitly
disabled in that process. The actor must have a different actual PID/start
identity, acquire its own original source frames and files, publish through its
own actor credential, and prove its own cleanup quiet interval. No actor token
is copied into the primary configuration, owner header or public facts.

## Actions and original evidence

The Android journey uses normal `open`, `capture-cancel`, `capture`, `save`,
`share-open`, `share-cancel`, `share-select-owned`, `upload-fail`, `upload`,
`background-resume` and `close` actions. SDK26–28 also requires the actual
`save-picker-open` and `save-picker-cancel` transitions. The independently read
platform selects `media-store` on SDK29+ or `document-picker` on SDK26–28, both
with `savePermission:not-required`. The common Photos permission actions are
conditional on the Photos backend; Android does not simulate those actions or
skip mandatory DocumentsUI transitions. Unsupported or missing platform,
resolution, provider or consumer sources remain failures.

Normal Open obtains the owned fixture account credentials, submits through the
actual login controls and joins the resulting native principal, token and
protected-request originals. Each role sample rechecks the original account
endpoint, owned principal, active credential and absence of pending login or
refresh work. Credentials are never archived. Capture cancellation joins the
visible original Review, native FastCancel recipe and original VM timer/work
history. Capture completion separately joins the reviewed actual script source,
native capture ID, original file prefix, actual FD close/inode/hash/bytes and
fresh render marker. Historical completion timestamps never become current by
being copied into a newer observation.

Save requires the actual native request/callback stream, the original OS
destination identity and independently reopened destination bytes. SDK26–28
additionally requires the separate DocumentsProvider's binding v2 floor and
full subsequent history, actual creator and Phone writer UIDs, original document
FD closure, independent provider binary and actual root/document retirement.
Share requires the real chooser/URI-grant context and the separate consuming
APK's actual ACTION_SEND read/close/hash; a chosen-component callback cannot
replace consumption. Upload requires the ordinary Upload control, original
native uploader lifetime and the actual HTTPS provider's retained multipart
receipt and independently acquired body. Private capture bytes cannot stand in
for any of these three exported originals.

Both roles retain immutable raw VM/native/input/provider/OS histories and
independently acquired PNG/binary inode receipts. During a real OS sheet they
use the prestarted passive native handoff source and the original narrow system
scope; they do not issue foreground-only client observations. A later Save or
Share phase retains the earlier actual capture marker ticket. Only a matching
current marker can qualify a new world-render PNG, including the mandatory
background/resume image. Original input receipts remain separate from the
effect reducer and the actor's independent witness.

SDK26–28 baseline arming retains the actual independent document-provider root,
binding floor and empty raw inventories as measurement ownership. That empty
setup alone is not a public live product resource. The first actual document
plan, created document or FD adds a document connection responsibility until
real provider retirement, including a created document whose writer has not
yet opened. Missing or disappearing prior originals remain failures. The
provider's actual raw DTO is retained in every role frame in either case.

## Bounds, failure recovery and complete retirement

The original source freshness window is 1.5 seconds and each ordinary source or
input exchange has its own real five-second monotonic deadline. A native
passive handoff lasts at most sixty seconds, cannot renew or revive, and the
facade permits at most four owned handoffs. Background recovery retains its
original twenty-second monotonic bound. Quiet checkpoints require actual
contiguous three-second intervals; the facade requires two distinct intervals
around restoration and the actor requires its own interval. The aggregate
catalog module budget is not a source freshness or checkpoint deadline.
Explicit synthetic native epochs used by host replay never replace these real
monotonic call/quiet bounds or qualify real device latency.

The separately credentialed actor keeps one flow for its actual process
lifetime. Cleanup uses two source-lock stages: first restore its own immutable
history and reader continuity, pin the verified feature/actor/role headers,
binding and cleanup activation, then release the lock. Preparation supplies no
current measurement or publication authority. On reacquisition, compare all
three actual headers and the binding both before and after loading. A changed,
otherwise valid header is refused rather than adopted.

Within the bounded current batch, each sample reopens and validates every old
original, acquires new current sources, and proves `restored()` from those
originals. The restoration metadata proof brackets its pure joins with two
complete input-history passes; it retains no metadata authority across calls.
After verified cleanup acquisition, the same actual actor may retain its reader
continuity between steps. Every step still checks all three original owner
headers before and after loading, reopens all old originals, and acquires a new
complete current sample. Reader lifetime is separate from trusted owner anchors:
`SnapshotPending` discards the reader but keeps only its own verified header
anchors for checked reconstruction. A known role header must match at the
constructor's first read; disappearance cannot create a new owner. Unexpected
failure or lock contention after qualified cleanup stops further use of that
flow. Contention before lock acquisition may retry with the same anchors.

Actual partial reads also retain their original native/avatar before packets as
continuity floors when no after packet was acquired. A present after packet
keeps priority and must validate; an empty or malformed after packet cannot
borrow a valid before packet. Diagnostic frames and their complete original
groups remain in the archive. These historical floors never replace new target
observations.

The actor lifecycle journal is now version 2, with a bounded, versioned history
of unpublished fixture-phase transitions. Exact process-bound version-1 state
can be read losslessly and upgraded only by its next own compare-and-swap save;
unknown legacy fields or a rollback of a retained actor's known save fail.
A role header cannot drop an already archived transition frame: its actual
manifest block must retain that frame's complete original prefix.

An ordinary actor acquisition admits its actual phase before reading native,
avatar or measurement sources. One proven owned activation advance can defer
that acquisition: two actual stable new phase observations and the old phase
are archived as a phase-only diagnostic. It claims no target state or measured
scope and produces no pending witness. The next step requires the new action's
actual acknowledgement or a genuinely cleaned owner before a fresh cleanup
acquisition and its own quiet interval. This also handles a logged-in ordinary
phase advancing to cleanup before logout can acquire the source lock. Account
validation is unchanged. An already completed stable frame observed under a
new ordinary phase remains an unpublished original, never a relabelled witness.
Closed/foreign/non-prefix/multiple phase advances, issued witnesses and existing
cleanup authority do not enter this recovery path. A phase change during actual
measurement still fails its original consistency checks.

`SnapshotHistoryReadPass` defines a single-use primary cleanup history boundary.
Construction requires the original source lock, current native authority, the
same existing SDK-session pin, and verified ready role/cleaned feature owners.
Between locks it uses isolated read-only engines to reopen every historical
manifest, frame JSON, PNG and binary, including genuinely planned absent PNGs.
All original bytes/hash/schema/image checks and per-file five-second bounds
remain. This host pass cannot acquire target facts, send input, recover or
publish. It records actual metadata around each full read and seals the exact
receipt collection; it returns only a historical graph digest.

On reacquisition, `finish()` requires the same process/thread, SDK pin, trusted
headers/binding, role state/history and cleanup activation. Actual owner inode,
mode, link count and modification/change metadata reject equal-payload header
replacement. Every original file and absence receipt is rechecked before and
after current native/phase authority, so a file changed after replay cannot be
hidden by the digest. The pass closes on success or failure before a new normal
role acquisition. The ordinary role history path retains its original locked
authority. Eight host test methods exercise this helper. The public observation
path is integrated with eleven stage/ownership cases and seven late-after-read
file/owner counterexamples. Both complete common replay qualifications remain
pending; these tests alone do not qualify the whole Snapshot composition.

The unchanged `quiet_window` requires at least three advancing samples spanning
three real seconds and resets after any gap greater than 1.5 seconds. An
incomplete batch saves its history and returns without a successful witness.
The four-second scheduling decision point is checked after a completed
acquisition; it is not a hard lock-hold guarantee. Earlier full-prefix host
measurements showed that the previous 3.5-second slice repeatedly yielded
before the first three-second quiet interval completed. Existing five-second
source/lock waits and all current freshness limits remain unchanged.

The production observer and the host actor call the same `poll_delay()` policy.
Only an owned retained cleanup reader with its anchor, watching state, quiet
history, no pending delivery and no failure uses a 50 ms pause. Ordinary,
bootstrap and busy paths retain 250 ms. This scheduling hint grants no target
or publication authority; the next step still validates every original and
acquires fresh sources. The cleanup pause leaves two opportunities for the
existing 25 ms source-lock contender poll. Actual fairness, complete lock holds
and the complete common deadline still need qualification together.

Primary cleanup no longer serializes an unchanged full history graph at every
owner comparison. Cheap checks still validate the current headers, role state
and binding. Full graph digests remain after preparation, before and after the
unlocked replay, and after the final native/phase guards before current IO.
The digest of the actually reopened historical graph remains separate. All
input-original reloads, actual file reads and receipt checks remain. Two pure
graph mutation counterexamples leave states, headers and files unchanged and
prove that the final digest rejects the mutation before the current reader.

Only its own newly acquired sample after completed quiet may be published.
Actual fixture closure, a new closed-phase read, fresh restoration and actor
retirement, actual process exit and repeated strict finalization remain
separate obligations. Earlier packet `7b6f40442c` qualified the former
one-acquisition-per-step implementation with six checks in 13.365 seconds;
it does not qualify this batch mechanism. The current parent integration
passed 72 source/host cases in 57.846 seconds, including owner-CAS and late
original/header changes during restoration. A late-history primary prototype
also proved a real quiet interval, but does not publish independent actor
facts. Seventeen resident-reader host counterexamples additionally pass at the
parent integration, with explicit native/header-load seams. The separate
[partial-read cases](../../../../android/phone/tests/device/test_snapshots_partial_read_resume.py)
execute actual acquisition, diagnostic archive and reconstruction. Earlier
bounded stress probes omitted the common primary loop's 0.25-second pause and
reset the actor quiet interval. A later bounded run with the actual common
primary and actor cadence at that revision, thirty additional primary frames and thirty actor
frames, retained ten advancing quiet samples without a reset; the largest
completion gap was 1.424 seconds. The separate actor acquired the actual shared
source lock once during each unlocked history pass. This scheduling check does
not qualify either complete SDK29+ or SDK26–28 common replay, which remain
pending, including strict ordinary-phase transition recovery.

The durable owner is written before setup can acquire settings, capture-file or
document leases. Baseline preparation takes readonly originals before ordinary
UI input. A failed first observation still attempts owned cleanup before the
fixture closes; a failure remains a failure after cleanup. With no issued
lease, partial cleanup preserves unknown initial UI and sends no normal input.
With actual issued leases it restores only those exact original settings/files/
documents and requires both quiet windows. `partial-cleaned` carries an explicit
original partial-retirement proof, never a successful baseline or an invented
actor witness. The separate actor accepts that proof only after original
fixture closure.

A qualified baseline can also fail before the first actual Save/Share request.
If the original readback source is still `initialized:false`, full cleanup
requires the unchanged complete original native export-history prefix since
baseline, no new owned export request, no active request and no pending IO.
That proof retains the actual unavailable DTO and native originals; it never
creates OS-destination or grant inventories. All real private capture files,
settings, current VM work, account, consumer/document and provider retirement
obligations still apply. An actual export request, foreign history or missing
baseline makes this branch red. A source/host owner test exercises actual
file/settings leases and both real three-second quiet windows after a qualified
baseline. Successful Save/Share checkpoints still require their initialized
version-2 independent export sources and original bytes.

Before fixture closure, normal animated Capture/FastCancel must actually delete
the owned uploaded story and native jobs/FDs/replies/callbacks must retire. The
provider's retained multipart body remains an unchanged private provenance
original until Client.close. Normal cleanup then deletes the original OS
destinations, revokes and checks URI grants, retires actual readback and consumer/
document workers, seals/deletes owned native/host capture files, restores the
original thirteen typed raw settings and native cache handle, logs out the owned
account and restores owned camera/input state. Unknown files, missing source
observations, pending work, failed deletes or foreign identities retain journals
and remain red. Empty public live capture history is allowed only after this
actual retirement; immutable historical events remain archived.

Contract v18 calls the same public cleanup operation again after the original
fixture has actually closed. The central dispatcher reads the nonce-bound
original phase before choosing normal cleanup or strict `finalize()`. The final
path additionally requires fresh provider `active:false`, zero uploads/stories/
inflight, actual retained-body absence, a new independent actor closed-phase
read, its original cleanup proof and actual process termination. It rechecks
all immutable PNG/binary originals and actual current native/file/work absence.
An immutable archive of the exact original owner and child headers precedes
their removal. Interrupted retirement resumes only from those originals; a
second completed cleanup needs the same archive, actual application binding and
fresh restoration checks. Missing journals alone never prove success. Global
adapter teardown attempts retained Snapshot cleanup even with the opt-in flag
removed and reports unresolved ownership after attempting base teardown.

Finalization validates the exact actor journal version and state shape. A
legacy version-1 archive is read without adding fields to its immutable bytes;
version 2 also reopens every transition manifest and frame and checks its
archived role prefix and typed scope. Current feature, retirement and child
headers authorize every historical read under the source lock. Fresh target
authority brackets the entire replay. Absent child headers are permitted only
for a verified interrupted retirement or a completed archived owner.
Five registered host cases exercise real TLS inputs, capture/save/upload,
phase transition, process exit and repeated finalization, including malformed
versions, missing originals, a foreign late process identity and a rolled-back
role floor. A separate held-exit case verifies that a retired actor which still
runs cannot authorize any archive or journal removal.

The historical compiler, Java/JNI, Qt, file, transport, reducer, actor and
recovery results above remain scoped host evidence. The current focused facade
suite has twenty-two passing cases, including actual private filesystem/journal
recovery and an actual separate actor process. Full public common SDK29+ and
SDK26–28 replay qualification is still pending; this document does not promote
Snapshot to the thirteen qualified Phone compositions. No hardware run,
installation, complete Android build, Proxmox laboratory result or device
acceptance is claimed by these source and host checks.

The fixed private native Snapshot, UI, FastCancel, Save readback and
upload-observation JSON outputs use the existing E2E-only atomic `QSaveFile`
publication path alongside
the handoff/settings/capture-file outputs. They require `--testScript`, reject
live or dangling symlinks, set mode 0600 and do not fall back to truncating an
existing file if atomic replacement fails. `test_snapshot_private_publication.py`
compiles the unchanged actual `saveObject` method with Qt6. It extracts all
58 actual fixed Phone/shared-feature output names from the original probe and
tests their publication on a real private host filesystem, including old-inode/hardlink
preservation, failed publication and the missing launch gate. Ordinary names
and a build without the E2E flag retain their existing writer behavior. Existing
general probe, voice and iOS/Pico output paths keep their original behavior.
The production allowlist remains literal names rather than a prefix grant. Only
the unrelated GPU receipt service is an unavailable host seam; the complete
scripting translation unit and Android client remain uncompiled by this check.

Historical replay performs fresh target-continuity checks before and after the
whole immutable host replay. Each intervening original/PNG/binary still checks
the exact locked feature/role header, binding, inode, owner, mode, link count,
actual bytes/hash and its file deadline. This host-only authority is never used
for current source acquisition, body transfer, input delivery or archive writes.
There is no history pruning, timestamp refresh or new expected-state source.
An actual target change at the final guard, changed old bytes/inode, or a target
change during a current native acquisition remains red.

With six real immutable role frames and six binary PNG originals, reconstruction
used 26 target guards before this change and two afterwards. With 41 immutable
input originals, baseline replay used 84 and then two. An explicitly synthetic
one-millisecond guard transport measured 44.205→18.768 ms and
127.145→23.582 ms respectively on the real host filesystem. These counts and
timings describe that host seam only. They do not establish device RPC cost,
real OS latency or complete common/actor qualification.
The same bracketed immutable input replay is used by lease preparation,
FastCancel observation/retirement, quiet-work floors and issued-input recovery;
none of those paths bypasses the final actual target check.

During a guarded current read, original-file intent callbacks use the private
host publication authority. The manifest-planned callback retains a fresh target
check before a complete frame can be committed; the acquisition also retains
its target checks around the archive. The saved original receipt and removal of
the fallback frame/work graph share one durable journal write. Outside that
guarded read, every callback still uses the complete current target guard.
`test_snapshots_storage_intent.py` covers actual save failures, lost replies,
ignored saves, original inode replacement, reconstruction and target changes.

Adjacent historical-floor comparison retains the previous canonical bytes
within one call. It preserves deep copies, full-row comparison and transitions
such as A→B→A; no history is pruned and no validation verdict is cached.
`test_snapshots_distinct.py` checks ordering, independent graphs, nested aliases
and the original comparison behavior. The parent join of these tests, role
recovery, publication guards and original cloning passed 44 tests in 10.401
seconds. This scoped result does not qualify the complete SDK26 common journey.

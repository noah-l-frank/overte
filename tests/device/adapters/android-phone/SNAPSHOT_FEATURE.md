# Android Phone Snapshot adapter continuation

The existing normal `snapshot.open/capture/files/close` implementation remains
the owner of the catalog's `snapshot-output-parity` foundation. It obtains
original files independently of input delivery. The common v17 extended
`feature.snapshots.*` triple is **not yet advertised** by the Phone adapter.
Devices and the complete Android client build remain unverified.

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
and complete public owner remain unfinished. Bounded binary acquisition below
now retains the completed Save readback in private host artifacts. This component must not advertise the extended Snapshot capability
or report a complete feature/cleanup verdict.

## Remaining composition

Implement normal review inputs, retain actual pending/cancelled UI observations
(including cancellation before native capture allocation), and establish
immutable process/run ownership. Join native capture IDs with
the actual unique capture filename, original bytes and a fresh fixture marker.
Do not infer capture completion from a button click or filename existence.

Android Save is `media-store` on API 29+ and `document-picker` on earlier
supported APIs; these require `savePermission:not-required`. Use the common
backend profile: do not simulate iOS Photos permission denial on Android.
Join the retained original Android request/URI identity to actual destination byte readback,
chooser cancellation and an explicitly owned receiver's independently read
consumed bytes. A chosen component ACK is insufficient. Upload failure/recovery
needs the controlled account service and independently retained multipart bytes
plus native completion, rather than replacing the upload input with HTTP.

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
desktop path with an explicit native observer seam. Full normal Qt fast-cancel
automation, extended owner, output cleanup and devices remain unfinished.

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
those independently from original producers. The public Snapshot triple stays
absent until its complete composition exists.

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

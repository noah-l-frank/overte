# Android Phone Snapshot adapter continuation

The existing normal `snapshot.open/capture/files/close` implementation remains
the owner of the catalog's `snapshot-output-parity` foundation. It obtains
original files independently of input delivery. The common v17 extended
`feature.snapshots.*` triple is **not yet advertised** by the Phone adapter.
Devices and the complete Android client build remain unverified.

## Passive native source v3

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

Version 3 additionally requires the original Android export source (export
component contract v1). The real Java adapter records its actual native handle,
ticket, Activity generation, original validated source path, original document
or MediaStore URI and callback values. Each request has a new opaque identity.
Insertion, completed copy, successful publication, actual deletion return
count, chooser selection, deferred result and native delivery are distinct
events. A read observes a deep copy under the recorder's lock; it cannot mutate
or reset any callback history. The bound is 256 original events; overflow,
unknown values, foreign/overlapping responsibility or clock regression leave
the source permanently incomplete. Source replays require the exact immutable
prefix. URI and source-path originals stay in the private evidence file.

The capture/review hooks require `OVERTE_E2E_FEATURE_TESTS`,
`ANDROID_APP_PHONE_INTERFACE`, `--testScript`, and the existing native test
lifecycle gate. The Java export recorder is instantiated only when its native
gate confirms that same Phone build and test-script process. The shared Java
source does not enable recording in other Android clients or ordinary builds.
The native read-only export method returns empty outside that gate or before a
real backend has initialized; an absent backend never becomes observed absence.
Capture, upload and export behavior is unchanged. In particular, a chosen
component and even the existing product `success` callback do not prove
successful system saving or receiver consumption. There is no destination byte
reader or receiver acknowledgement in this source contract.

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

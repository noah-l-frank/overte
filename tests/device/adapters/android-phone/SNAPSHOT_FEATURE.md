# Android Phone Snapshot adapter continuation

The existing normal `snapshot.open/capture/files/close` implementation remains
the owner of the catalog's `snapshot-output-parity` foundation. It obtains
original files independently of input delivery. The common v17 extended
`feature.snapshots.*` triple is **not yet advertised** by the Phone adapter.
Devices and the complete Android client build remain unverified.

## Passive native source v1

`phone-snapshot-observe` accepts exactly `schemaVersion:1`, a fresh 32-character
hexadecimal `commandId`, `action`, and the 32-character hexadecimal `runId`.
There are no capture, export, expected result, filename or state inputs.
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

All hooks require `OVERTE_E2E_FEATURE_TESTS`, `ANDROID_APP_PHONE_INTERFACE`,
`--testScript`, and the existing native test lifecycle gate. Ordinary builds
contain neither the recorder member nor the observation method. Capture and
upload behavior is unchanged. An observed terminal callback alone does not
prove image content, successful system saving, receiver consumption or upload.

## Remaining composition

Implement normal review controls with original component identity, actual
pending/cancelled UI history (including cancellation before native capture
allocation), and immutable process/run ownership. Join native capture IDs with
the actual unique capture filename, original bytes and a fresh fixture marker.
Do not infer capture completion from a button click or filename existence.

Android Save is `media-store` on API 29+ and `document-picker` on earlier
supported APIs; these require `savePermission:not-required`. Use the common
backend profile: do not simulate iOS Photos permission denial on Android.
Record original Android request/URI identity, actual destination byte readback,
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

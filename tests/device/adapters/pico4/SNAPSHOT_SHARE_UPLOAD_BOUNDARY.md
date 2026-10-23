# Pico Snapshot Share and Upload continuation boundary

This is a source audit following the private normal
[Save owner](SNAPSHOT_SAVE_OWNER.md), not execution/acceptance evidence. The
shared recipe remains v16 and its actual Share sequence precedes Upload.
Neither an isolated later component nor a Phone witness can fill that gap.

## Existing product route and missing ordinary chooser driver

The existing `NativeSnapshotReview.qml` exposes System share through the normal
image-row button (`scripts/system/snapshot/NativeSnapshotReview.qml:265`). It
calls the existing `platform.request(path,"share")`; no new button/backend is
needed. `SnapshotAdapter.java:239–255` creates a FileProvider URI using the
actual Activity package plus `.snapshot.files`, attaches the actual URI as both
`EXTRA_STREAM` and ClipData, grants read permission, and starts the original
system chooser. The Pico authority is therefore `org.overte.pico.snapshot.files`.
The existing chosen-component callback is original selection history; it is not
proof that a separate recipient opened, consumed or closed the stream.

`tests/device/adapters/pico4/navigation.py:600` requires the original app/process,
bound Pico session and `org.overte.pico` foreground for its normal Qt/controller
input. Once a different chooser Activity is foreground, that app-only route
cannot select its row. Keep those guards unchanged. The existing
[controller decision](../../openxr_input/PICO4_CONTROLLER_AUTOMATION.md)
defines an app-packaged OpenXR layer, explicitly excludes the OS-reserved system
button and rejects Android framework key events as XR-controller evidence. An
Android touch/DPAD injection is not an observed Pico controller action in a
foreign system Activity.

At fixed read-only Phone commit
`97219dbebc90ee95db943e5bf82a577b75a04e8e`,
`overte_phone_snapshot_system_ui.py` observes the actual Appium accessibility
tree/current Activity and sends `/actions` with `pointerType:"touch"` or `/back`.
Its exact source/intent/re-read guards are useful design references. Its input
cannot be renamed as ordinary Pico VR input. No competing generic input system,
foreground-guard exception or explicit-target chooser shortcut is introduced.

## Independent recipient is a separate actual source

That fixed Phone `SnapshotReceiverState.java:38–42` accepts only authority
`io.github.noah_be.overte.phone.snapshot.files` and resolves the actual provider
package as `io.github.noah_be.overte.phone`. The corresponding strict Python
`overte_phone_snapshot_consumer.py:source()` has the same identity boundary.
Neither currently accepts the actual Pico provider. Merely copying the Phone
reader would reject Pico, while changing only the reader would invent source
compatibility that the original receiving APK does not provide.

The reusable existing ACTION_SEND consumer obtains the URI/ClipData and read
permission from the real received Intent, resolves the real provider UID,
opens/closes the real stream and records its independent private copy. Its
DUMP-protected observation/binary transport pins the separate APK digest,
UID/PID/start identity and original source birth. A future explicit test-only
Pico source version must preserve these actual facts, ordinary chooser
selection, independent receiver/hash acquisition and one-send grant/copy/worker
retirement. No installation or device action was performed in this audit.

## Upload can reuse its genuine network provenance

The existing normal Upload for URL button is already in the product. It requires
the actual logged-in/canShare state (`NativeSnapshotReview.qml:266`). Original
`scripts/system/snapshot.js:163–175` reads actual domain-share authorization and
login state before `Window.shareSnapshot`; an input ACK does not satisfy either.
`Snapshot::uploadSnapshot` (`interface/src/ui/Snapshot.cpp:725–785`) opens the
actual file, creates the multipart body and sends the authenticated snapshot
POST. `SnapshotUploader::uploadSuccess` reads the actual image response and
sends the separate story POST; `complete`/`cancel` retire the original uploader
through its ordinary `deleteLater()` path.

The same fixed Phone commit provides
`libraries/networking/src/PhoneSnapshotUploadEvidence.h` plus passive original
Snapshot/AccountManager hooks, and strict `overte_phone_snapshot_upload_source`,
`upload_fixture` and `upload_bytes` readers. The evidence captures actual file
descriptor bytes, actual consumed stream digest, original multipart boundary,
request/reply IDs/status/body digests, and actual file/multipart/reply/uploader
destruction. The independent HTTPS fixture joins its own retained body/reply
files and receipt IDs; callback success alone cannot qualify Upload.

Those are source candidates for an explicit Pico test gate/normal control and
existing private source lock. No URL setter, direct `shareSnapshot` call,
requested upload result, hidden endpoint rewrite or Phone mono/touch evidence
is admitted. Any later Upload component remains partial until the real preceding
Share steps, original authorized domain/login, independently received TLS
bytes, failure/recovery, restored state and complete resource obligations join.

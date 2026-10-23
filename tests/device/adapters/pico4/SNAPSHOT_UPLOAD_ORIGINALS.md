# Original Pico Snapshot upload source

The private `_snapshot_upload_source(target, source_lock=...)` factory reads
actual client upload provenance under the exact existing Script source lock.
It exposes no Upload/Cancel/URL setter. The whole Snapshot feature remains
partial: no Pico Share/Upload/Resume/cleanup journey is advertised by this
source, and an upload callback or input ACK is never its independent result.

## Fixed provenance and existing normal controls

The native collector and strict reader were selected read-only from frozen
Phone `b62e012f1328e30b80604bb447a60db0d8a748df`, specifically
`libraries/networking/src/PhoneSnapshotUploadEvidence.h` and
`tests/device/adapters/android-phone/overte_phone_snapshot_upload_source.py`.
Its previously reviewed `97219dbebc90ee95db943e5bf82a577b75a04e8e` is an ancestor.
No moving Phone worktree, Phone UI facade or touch/mono evidence is imported.
The adapted Pico source names and paths are distinct; old Phone source version
one is not admitted as Pico version two.

The actual existing `NativeSnapshotReview.qml` Upload control is already
exported by the ordinary `native-pico-snapshot-export-v1` control path. Its
pointer/`sendToScript` behavior is owned by the existing
`snapshot-export-originals` Qt harness. The script's real login/domain permission
checks and the existing `Window.shareSnapshot`/`Snapshot::uploadSnapshot` path
remain in force. This packet adds no button, login result, backend endpoint,
forced domain permission, direct upload invocation or product repair.

The dedicated `OVERTE_E2E_FEATURE_TESTS` plus `ANDROID_APP_PICO_INTERFACE` build
gates add passive hooks at original uploader construction/cancel/completion,
actual opened QFile and QHttpMultiPart, original image/story request tickets,
and AccountManager's actual QNetworkReply before its existing ticket/receiver
callbacks. The collector additionally requires the original `--testScript`
process boundary. The TSI getter retains the private results directory,
lifecycle, active app/HMD, actual TSI thread and bounded weak dispatcher guards.
It reads the process-lifetime collector without passing a foreign raw QObject
association between query threads. A busy collector observation fails closed.

## Original bytes and precise lifetimes

The already-opened original file must match its uploader path. Its actual FD
must be a regular, singly linked owner file with private permissions. A bounded
`pread` hashes its actual complete bytes without moving the normal QFile read
position. Full original device/inode/size/mode/UID/GID/link/mtime/ctime values
must agree before and after that read. Device and inode are decimal strings so
JSON cannot round a 64-bit identity. Actual later QFile `readData` consumption
has its own byte count/hash; those facts can disagree, in which case a future
independent backend join must fail rather than substitute the pre-read digest.

File liveness becomes false from actual `QObject::destroyed`, after QFile's
normal close/destruction, instead of the earlier derived-file destructor point
in the frozen source. A close alone deliberately leaves the QObject retained.
Original multipart, uploader and reply destruction have distinct facts.
Actual request URL/auth-presence/operation/multipart boundary/JSON-body hash,
upload progress, terminal status/error/fixture-response-header and peeked reply
bytes are retained; peeking does not consume the normal callback's reply body.
The collector is process-lifetime bounded history with no reset/retire API.
Nothing here proves global networking, maps, executors or callbacks retired.

The closed query `feature-pico-snapshot-upload` accepts only schema, command ID
and run ID. Probe dispatch publishes the actual whole DTO once to private
`feature-pico-snapshot-upload.json`, or unavailable. Both native and host readers
retain source cursors; current acquisition validates complete original raw bytes
and both native/monotonic age bounds after final copy/guard work. Cold restore
requires exact typed raw JSON and never sends a command. Strict source metadata
version two and wrapper version one are registered with REQUIRED compatibility.

## Device-free verification and remaining joins

The native harness compiles the actual collector, entire original
`SnapshotUploader.cpp` and moc, original `JSONCallbackParameters` class and
constructor, original AccountManager observation hook and whole original TSI
getter. It exercises real host file bytes/FD metadata/read hash, actual Qt
QObject/deferred destruction, bounded blocked dispatch/late-functor rejection,
normal original story payload/cancellation and four build/runtime gate profiles.
Backend/window services, reply data/signals and HMD status are explicit host
seams; it performs no network or Android operation. The real host pathname is
retained honestly: its file metadata validates, while the complete Pico reader
must reject that host path as target evidence.

Focused reader/factory/Probe counterexamples use explicit native DTO transport
seams and actual Pico candidate/process/session/foreground guards. They verify
closed read-only commands, unchanged parent lock, lossless FD IDs, rewritten
file metadata/history/lifetimes, old Phone/host paths, current query freshness
with either clock frozen, raw bounds before decode and no cold input. The new
`snapshot-upload-originals` selector owns these cases and its native harness;
the capability matrix adds that selector without weakening any source check.

A normal Upload owner still needs exact parent Still/Save originals and intent
before its real normal control, fresh domain/login/backend authority, a new
original job/tickets, independently retained TLS image/story bytes and reply
receipts, actual failure/recovery/cancellation, return and three-second quiet.
The existing fixed Phone TLS fixture/join is a reuse candidate, not an executed
Pico backend. Missing ordinary chooser VR input and a Pico-qualified independent
receiver remain [explicit Share boundaries](SNAPSHOT_SHARE_UPLOAD_BOUNDARY.md).
No device, SDK26, rendered fidelity, whole recipe or complete cleanup claim is
made from these source/compiler checks.

The owning selector passed eleven cases in 13.213 seconds; coverage passed
alongside it (two groups in 13.28 seconds). The actual native source/getter/
uploader harness also passed separately with the prepared Qt5 installation;
its four compile profiles include Pico E2E, Phone E2E, other E2E and production
Pico, with and without the runtime test flag. Those are host/compiler checks
under the declared seams, not Android/native-client or real TLS results.

Valid native query IDs are consumed before original acquisition, including an
actual collection that exceeds the private 200-KiB raw-source bound. The native
harness creates that original oversized collection from explicit reply-signal
seams, observes unavailable and proves the same query cannot be retimed later.
Malformed commands do not consume admission. Source history/rows remain intact.

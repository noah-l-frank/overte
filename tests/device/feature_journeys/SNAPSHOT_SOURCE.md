# Snapshot source audit for the next common contract correction

The current common v8 Snapshot journey still has source mismatches. Do not
activate a complete Snapshot adapter against that draft. This audit records
actual source behavior; the corrected versioned scenario and adapter composition
are implementation work, not device evidence.

Reviewed product bases are Phone `718d069add`, Pico `c5bf8ac17b` and iOS
`864f8b79a4`. Current local platform branches retain these functional sources.

| Source | SHA-256 of original bytes |
| --- | --- |
| scripts/system/snapshot.js (all three) | 7de92f3be9b803d76f4adea1b267b509003499a860e95f447bdbcc12a9545c57 |
| android/common/snapshot/java/org/overte/snapshot/SnapshotAdapter.java (Phone/Pico) | 8810120f160d86bfc398c99e2cc790940bdcb753bfe6a11c61bea0ca25fb8c23 |
| android/common/snapshot/src/NativeSnapshotAdapter.cpp (Phone) | 400ab88652be1def4b8380718ffc69ff9774219095344e8f11899f4c92851a42 |
| ios/snapshot/IOSSnapshotAdapter.mm | e9c0ebd2922f2f92c8e603bbdecfc53c1628966ef95188df38c3e745bbe61744 |

Hashes identify reviewed source, not a loaded component or installed binary.

## Capture and cancellation

The normal Snapshot script permits a local private capture without a network
permission lookup. Native capture has an original request ID, pending delays,
render/encode work and real status callbacks. `cancelNativeCapture` invalidates
the ID, clears timers, calls `Snapshot.cancelCapture` and reports cancellation
only when a request existed. An idle cancel is vacuous. The corrected journey
must first observe an actual pending owned capture (for example animated), then
cancel through normal UI and independently check original private files and
late callbacks for a full negative observation window. Do not add artificial
product success, failure or delay setters as instrumentation.

A denied Photos permission does not deny private capture. Android Save requires
no storage permission. The v8 `set-storage-permission` / denied-capture sequence
must be removed rather than implemented with a fabricated permission error.

## Distinct normal Save backends

| Actual backend | Normal behavior and required test |
| --- | --- |
| iOS add-only Photos | Save requests actual add-only authorization, then a Photos creation transaction using the original file URL. Denial fails Save while retaining private capture. Recovery must come from actual OS permission/settings input; another real Save must produce an independently read saved original. |
| Android API 29+ MediaStore | Save inserts a pending image, copies/closes original bytes and publishes the row. There is no runtime storage permission or Save chooser to deny/cancel. Read the actual published owned row and original bytes; a callback alone is insufficient. |
| Supported Android below API 29 document picker | Save uses ACTION_CREATE_DOCUMENT. Observe the actual chooser before cancellation, or select an owned destination and verify actual copied bytes after return/focus. An existing unrelated user document must never be deleted as cleanup. |

A real backend/version policy must be measured and pinned independently before
choosing applicable permission/chooser checks. Unsupported or absent native
export backends must fail the mandatory capability gate, not become a green
platform skip. Conditional checks must not omit common capture, successful Save,
share, upload, resume or cleanup obligations. Original permission state and
pre-existing files must be preserved under explicit owned test setup.

Photos cancellation during authorization cannot dismiss the OS prompt; the
native lease waits for the actual answer. Once Photos commits, cancellation
waits for the real result and cannot claim rollback. Android late returns are
bound to Activity/request/generation and genuine foreground/focus restoration;
chooser launch or Activity return alone is not a successful saved file.

## Share, upload and cleanup

Share must first expose an actual system sheet/chooser. Cancellation before
selecting a receiver creates no recipient result and retains the private capture.
The successful path requires an independently owned real receiving endpoint to
read the granted original bytes. iOS activity completion and Android chooser
selection prove handoff only, never that an external receiver stored the file.
Do not copy the private capture into the actor's directory to manufacture that
receipt. Capture, saved destination, receiver output and upload server body have
different original ownership/acquisition sources even when their bytes match.

Upload failure/retry requires actual requests and owned authenticated server
receipts; a selected UI item, queue entry or locally echoed status is insufficient.
Cleanup independently enumerates every owned private capture, OS destination,
receiver output and server delivery, drains pending native leases/late callbacks,
and restores the original settings/permissions. An OS commit or external delivery
cannot be withdrawn by merely closing the review or killing the app.

The v8 witness currently includes only file/upload/share counts. The correction
must also independently witness actual pending state, review/system sheets,
backend/permission and errors, with original artifact provenance for each sink.
Existing `snapshot-output-parity` remains the owner of still/animated/panorama/
cubemap decoding; extend it rather than creating a parallel output runner.

The existing ten `tests/javascript/test/snapshot.production.test.js` cases are
now registered in the common control-plane selection through
`test_snapshot_source_semantics.py`. They run the original script on explicit
synthetic native/timer seams: normal modes/preferences/readiness, pre-render
cancellation, old callback rejection, GIF review, upload cancellation/errors and
shutdown. They do not execute renderer, OS export services or a full feature
scenario, and do not correct the v8 common draft by themselves.

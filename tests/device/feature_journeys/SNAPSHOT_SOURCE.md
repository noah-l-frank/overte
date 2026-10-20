# Snapshot source and adapter boundary, common journey v9

Version 9 corrects the source mismatches found in the v8 draft. It separates
private capture from real OS Save, observes actual pending-cancel history and
system sheets, and requires original destination/receiver/upload bytes. This is
common test logic; full native adapters and physical evidence are still missing.

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
only when a request existed. An idle cancel is vacuous.

The v9 `capture-cancel` action is a fast ordinary UI recipe: select animated/PNG,
click Take snapshot, independently record the actual new pending request and
normal QML capturing state, then click its real Cancel button **before renderer
submission**. There is only a 350-ms first delay before the script hides the
tablet; do not insert a 0.5-second common poll or host round trips before Cancel.
Use bounded local target automation on the original visible controls. It may
observe/retry reads; it must not invoke the script handler, change delays, set
properties, pause the event loop or call Snapshot.cancelCapture as an input.
If the actual pending state or Cancel button cannot be observed/reached within
that window, fail and retain cleanup intent; never replace it with idle Cancel.

`captureHistory` is an original immutable sequence for this run's owned request
contexts: `pending,cancelled,pending,complete` over the two capture attempts.
`pending` comes from the actual script request ID/scheduled work plus its real
clearPreviousImages/capturing transition; `cancelled` requires that same still
active original request and actual cancel callback/timer retirement. `complete`
requires the next actual native complete callback. A requested click, command
sequence or future expected phase is no substitute. Both primary and independent
actors freshly acquire the original context/sequence/time-correlated history;
neither copies the other's normalized checkpoint. Stale/foreign request callbacks
must not append phases. The common negative window then requires no original
files or late completions, pending false and the real cancellation history for
three seconds. Cancel after a still file has already been written cannot claim
that file never existed.

`open` identifies the actual SNAP review route (`AppUi.isOpen`), whose visibility
is separate while Snapshot temporarily hides the tablet. Capture completion
normally restores the tablet. A successful private still/PNG must be acquired
under its original capture challenge even when Photos Save is denied. Android
has no runtime storage permission to deny. The v8 `set-storage-permission` /
denied-capture sequence is rejected by the v9 action grammar.

## Distinct normal Save backends

| Actual backend | Normal behavior and required test |
| --- | --- |
| iOS add-only Photos | Save requests actual add-only authorization, then a Photos creation transaction using the original file URL. Denial fails Save while retaining private capture. Recovery must come from actual OS permission/settings input; another real Save must produce an independently read saved original. |
| Android API 29+ MediaStore | Save inserts a pending image, copies/closes original bytes and publishes the row. There is no runtime storage permission or Save chooser to deny/cancel. Read the actual published owned row and original bytes; a callback alone is insufficient. |
| Supported Android below API 29 document picker | Save uses ACTION_CREATE_DOCUMENT. Observe the actual chooser before cancellation, or select an owned destination and verify actual copied bytes after return/focus. An existing unrelated user document must never be deleted as cleanup. |

A real backend/version policy must be measured and pinned independently before
choosing applicable permission/chooser checks. The measured initial Photos
add-only authorization must already be granted in the owned fixture setup;
Android must report not-required. An unowned/unsupported initial state fails
before input, not a green skip. The initial backend/authorization is retained
exactly for independent cleanup restoration. Unsupported or absent native
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

The v9 witness includes all twelve state fields, including actual pending
history, review route/system sheets, backend/permission and errors. The 18-row
closed inventory has 15 applicable Photos checkpoints, 12 MediaStore checkpoints
and 15 document-picker checkpoints. Only the Photos permission/denied-Save and
document-picker open/cancel rows are conditional; all common flows stay required.
Unknown backends are errors. The runner records the pinned source profile and
non-applicable row indices explicitly, never as executed successful actions.

The private PNG is decoded and its actual SHA-256 retained by the runner.
Subsequent file evidence must come from the actual OS-saved original, real
receiver or authenticated upload body and match those captured bytes. Snapshot
file artifacts require the corresponding closed `source` acquisition category;
relabeling a copied private capture as an external receipt is prohibited. The
independent actor must read the actual endpoint and its original result, rather
than echo native success/chooser selection or copy the primary adapter's state.

System-sheet/settings rows may produce actual deactivation/background/activation
notifications. Their counters must be monotonic, bound PID and launches must
stay unchanged, and the final native counters must settle for the normal
observation window before being pinned for the next checkpoint. No counter is
incremented by the runner as a claimed OS event. Other lifecycle inputs retain
the existing exact notification requirements.
Existing `snapshot-output-parity` remains the owner of still/animated/panorama/
cubemap decoding; extend it rather than creating a parallel output runner.

The existing Snapshot JS suite, now eleven cases with an added idle-Cancel
counterexample, is
now registered in the common control-plane selection through
`test_snapshot_source_semantics.py`. They run the original script on explicit
synthetic native/timer seams: normal modes/preferences/readiness, pre-render
cancellation, old callback rejection, GIF review, upload cancellation/errors and
shutdown. They do not execute renderer, OS export services or a full physical feature
scenario. Seven v9 common counterexample groups separately exercise all source
profiles, false pending proof, ignored effects/sheets, permission/error mismatch,
missing external results, wrong file source/changed original bytes, backend
replacement, native lifecycle continuity and incomplete cleanup. These are
hardware-free test-logic checks only.

Before platform activation, qualify the actual OS/settings/chooser lifecycle.
The current source profile preserves the same primary process across system UI;
an OS version that terminates the app on permission changes cannot be accepted
by relabeling that replacement or inventing counters. It needs an explicit
reviewed restart/ownership profile before advertisement, or a concrete unsupported
profile failure. A real independent Photos/MediaStore/document/receiver actor
with permission to read and remove only this run's originals is also required;
the primary add-only Photos grant does not itself authorize library enumeration
or cleanup. These are full-adapter activation prerequisites, still unimplemented.

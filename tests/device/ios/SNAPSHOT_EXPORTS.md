# Original native Snapshot export observations

The passive `feature-ios-snapshot-exports` query uses the existing guarded
HTTP/AFC source transport. Its command contains only schema, nonce, action and
run identity. Native code samples actual Photos add-only authorization, export
operation state, owner/sheet presence, immutable callback history and weak
operation lifetime. The test probe preserves the native response unchanged and
does not repeat a source nonce. No complete Snapshot capability is advertised.

`IOSSnapshotAdapter` records its actual authorization, Photos transaction,
system activity completion and Qt delivery callbacks. Callback entry and return
are separate events. The actual Photos placeholder is only a creation identity;
the actual transaction completion is a separate native result. Weak pointers
retain no application export object. An operation kept by a Photos, UIKit or
Qt callback remains visibly alive after an input/result acknowledgment.
Atomic native operation state is read once per sample, and the original weak
lifetime sample clock is obtained after inspecting the owners. Foreign export
filenames and Photos identifiers are redacted. `owned` identifies the controlled
Snapshot filename grammar; a particular run additionally matches its original
prefix, exact normal input/capture owner and original private capture bytes.

The observer is compiled only for the dedicated iOS feature configuration and
requires `--testScript`. Outside that configuration event macros evaluate none
of their arguments. Observation neither requests authorization nor reads,
creates or deletes a Photos asset; it neither opens nor dismisses a sheet.
The existing product request, commitment, cancellation and completion decisions
are unchanged. The native getter also requires the actual Qt GUI/UIKit thread.

The closed Python decoder preserves source births, original native epoch and
monotonic clocks, operation identities, complete immutable event prefixes and
weak expiry. Historical Photos success must include the real committed
transaction, placeholder, native completion and Qt callback result. It cannot
be reassigned to another query run. `destinationOriginalRequired` remains true:
no helper returns a public saved/share count or treats native success as proof
that a destination retained the actual capture bytes. Drainage requires actual
weak expiry and returned callbacks, including foreign outstanding operations.

Seven source/transport/weak-lifetime host tests include native success while a
callback owner remains alive, cancellation, wrong-run success, missing commit,
altered history/birth/PID/nonce/clocks and the actual one-send probe branch.
These use explicit host producers for native Photos/UIKit facts. Objective-C++
and UIKit/Photos remain uncompiled; no device, installation or lab is accessed.

Remaining Snapshot integration includes actual pending Script/timer/render
cancellation before submission; normal OS authorization and activity inputs;
independent saved-original Photos bytes and deletion of only owned assets;
an actual external share recipient; authenticated upload/body receipts; and
paired fresh image/source/quiet cleanup. Add-only Photos completion alone
does not provide the read permission or independent original destination bytes
needed for those checks. Existing native file-reader self-tests compile native
helpers and are intentionally not run in this no-build session.

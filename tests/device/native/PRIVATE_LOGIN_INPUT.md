# Private login input lease, version 1

This is a private credential carrier and cleanup prerequisite, not an
Authentication result or complete feature adapter. Common journey v6, control
metadata v2, actual protected profile/UI/backend witnesses and all platform
qualification remain separate. Native C++ is uncompiled and unexecuted.

## Public metadata and private payload

The existing fixture/probe carries exactly schemaVersion:1, commandId (ios- plus
fresh 32-hex), action:"feature-private-login-input", operation, runId and inputId
(both 32-hex). Operations are inspect, reserve, deliver and retire. The public
route rejects text, input bodies, expectations and all other fields. Neither
public command, status nor ownership journal contains credentials, lengths or
secret digests. A missing native hook yields unavailable, never success.

The only data carrier is feature-login-input-<inputId>.v1.json in the explicitly
owned native private test root. It has exactly schemaVersion:1, runId, inputId
and input. Input is exactly schemaVersion:1, commandId/instance/fieldToken (original
non-null native UI UUIDs), sequence, observedElapsedMs, operation:"replace" and
text. Text is nonempty printable ASCII, at most 4096 UTF-16 units. Total input is
at most 16384 bytes, sorted compact canonical JSON plus newline. This detects
duplicate keys/alternate spellings before dispatch. These bytes are inputs,
never measured product state or evidence of successful login.

The native source owns the 0700 same-user canonical root and exclusively creates
a 0600, single-link regular empty original. It pins root and file device/inode
and keeps the original descriptor through retirement so inode recycling cannot
adopt a copied file. The actual platform must write that original **in place**
through app-private storage. An upload implementation that replaces its inode
is unsupported; do not weaken ownership for it. Host independently reads back
actual private bytes after upload. An ACK or returned expected payload is not
this readback. No HTTP/probe/CommonJS path carries the data.

Reserve requires the separately owned native account-origin document for this
run. It changes neither product URL nor native trust. Only one lease may remain
active. New reservations are bounded to 4032 records, leaving 64 final retirement
slots; no history eviction can admit an old nonce again. Native root/context
replacement, wrong owner/mode, links, foreign original or unavailable origin
refuses delivery. Unknown files cannot be adopted from their valid-looking bytes.

## Native observations and input

Receipts have exactly inputVersion:1, commandId, operation, runId, inputId,
instance (actual private source birth nonce), processId, capturedEpochMs,
elapsedMs, sequence, available:true and source. A source contains reserved,
retired, attempted, filePresent, fileOwned, pending (actual booleans) and openFiles
(actual retained original input descriptor count, 0 or 1). An unavailable source
is rejected rather than treated as empty. Native and host clocks are not equated
on iOS: fresh command identity, original native source/sequence/clock continuity,
actual process binding and bounded transport establish the source scope.

Delivery consumes the input attempt before dispatch and never replays uncertain
normal input. It reads the original file under bounded same-inode/type/owner/link
checks, validates run/nonce/body, re-reads its actual unchanged bytes and verifies
the current root before invoking the platform's real GUI input owner. The original
is unlinked and its retained backing descriptor truncated and observed empty
**before** GUI dispatch. Parsed/raw input is not retained after that call.

The platform callback must resolve only the actual username/password controls,
check current native account and generic submission endpoints against the
independently provisioned origin, bind the original native UI instance/token/
sequence/focus and deliver ordinary IME input. It cannot call a login handler,
assign a field property, change authority, bypass native TLS or synthesize a
feature result. GUI work is synchronous on its actual owner thread; reentrant
private requests are refused while pending. Source-file parsing alone performs
no product input. Missing platform callbacks keep the producer unavailable.

An attempted input may retain an original inputStatus with exactly schemaVersion,
commandId, instance, sequence, performed, processId and sampleEpochMs. This is the
actual native GUI delivery metadata, filtered before retention/receipt. Its
original time and identity remain immutable on later reads. It establishes no
principal, protected access, persistence or remote authority. Native protected
profile/backend/UI effects are still mandatory for a complete Authentication
verdict.

## Retirement, deadlines and recovery

Retire marks the nonce before cleanup, including a never-reserved original, so
delayed reservations/delivery cannot apply later. It removes only its exclusive
original, truncates actual retained backing data, verifies disappearance and
closes its original descriptor. Partial/oversized/mode-failed writes in that
original can be removed; replacements, different owners or extra links remain
unresolved. Fresh inspection reads actual filesystem and descriptor inventory.
An empty path with an open original descriptor is not complete cleanup.

The host records binding/run/input nonce intent in the existing 0600 private
state mechanism **before** reserve/upload. It pins original native source
identity, advancing sequence and nonregressing original clocks. No text or
secret hash is written to that journal. Input is bounded by a total 15-second
budget; receipt polling has at most 51 reads per request. Retirement has one
five-second total budget including mutation and two independent fresh inventory
reads. Stalled/reversed clocks, lost nonce, missing native result and late
transport cannot pass. Only retired:true, filePresent:false, pending:false and
openFiles:0 permit journal removal. A retire ACK alone is insufficient.

An uncertain input is never replayed. Its own file lease is retired even after
failed upload/delivery; failed cleanup retains the private journal. Recovery must
match the actual original source/process/session context. Intentional app restart
must retire this scope first; a new process cannot adopt old originals. The outer
Authentication owner separately retains actual UI/input intent and must close its
owned view, clear product authority, drain native probes/origin, revoke fixture
authority and verify overall cleanup. Retiring this file does not undo product
input or prove native logout. Metadata transport receipts are not product file
artifacts; their owning fixture/session teardown remains a separate obligation.

Sixteen device-free cases use real local private files/descriptors with an
explicitly synthetic native seam. They exercise ignored upload/input, original
readback, copied foreign inode, lost process, stale/foreign/pending receipts,
missing native results, false cleanup ACK, retained FD, durable-context recovery,
invalid public/private payloads and actual JavaScript dispatch. They prove carrier/
ownership logic only. No native Qt/UI/AFC behavior, installed client or device is
qualified. Platform private transfer/callback/cleanup integration is still required.

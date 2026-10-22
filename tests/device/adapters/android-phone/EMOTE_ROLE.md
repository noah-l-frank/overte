# Phone Emote role observations and motion files, version 1

`PhoneEmoteRole(run, role, image_policy)` composes the actual Run v4, checked
Source v4, ordinary Input v2, Effects v2, Observation and private file owners.
It is an internal component, not a registered complete feature adapter. Scripts,
Authentication and Graphics remain the only three complete Phone triples.
Native instrumentation remains uncompiled and all device behavior untested.

Construct under the real run's held source lock, after loading its unchanged
parent journal. Role is exactly `primary` or `actor`. Image policy is exactly
`{source:"world-render-target",marker,subject}` using the existing rectangles.
Run, fixture, actual candidate/process/session binding, approved source policy,
namespace and private artifact root come from the real parent and sources.
No expected effect, image, animation name, pose or peer fact is accepted.

## Acquisition and original records

`read(after_sequence)` always acquires a new role-local source measurement.
It never re-emits a stored public result. The caller's cursor must be an integer
0..1024 and cannot exceed this role's durable sequence. The same source lock
serializes target transports; actor and primary retain separate original source
streams and public sequences. The parent must be prepared for baseline, active
with the exact actual call for normal input, or resources-restored for cleanup.
Normal observations reopen the pinned original admission; each current source
also checks actual executable membership and world approval independently.

The role control `phone-emote-<role>-role.json` has exactly
`{emoteRoleVersion:1,runId,fixtureUrl,role,binding,artifactRoot,imagePolicy,payload}`.
The existing bounded packed payload holds one
`{phase,segment,index,sequence,manifests,last,played,lastImage,compare,pending}`.
Phases are ready, acquiring and retaining. Segment is 0..15, index 0..256 per
namespace, sequence 0..1024 for successful retained observations. Last is the
sequence or null. Played retains the role's own original play reference, never
the other role's measured state. LastImage/compare are `{segment,record}` or null.
Every manifest uses the existing 128-entry immutable original index protocol;
controls remain limited to 64 KiB and each role original to 1 MiB.

Pending is exactly
`{ticket,image,index,scopeId,motion,original,manifest}`. It is durable before a
source acquisition, scope creation, artifact creation or archive transfer.
Original and manifest intents use the existing planned/opened/saved protocol.
Scope ID is persisted before reading that actual scope. No original file is
replaced or adopted by filename. Successful scope transfer retains the complete
historical context before removing child metadata.

A role original contains exactly
`{emoteRoleRecordVersion:1,sequence,segment,index,ticket,image,archive,effect,frame,inputHeader,inputSourceHeader,sourceHeader,played,background,motion,public}`.
`stored(index)` reopens immutable files and reconstructs the actual native,
input, image and motion proof. Public resources, lifecycle, artifacts, state,
ticket and epochs are recomputed from those originals. Subsequent records must
advance the original native sequence/evaluation and preserve process/history
continuity; changing the public sequence cannot make an old sample new.
Historical replay performs no target/fixture query and does not assert current
freshness. Missing, changed, replaced, foreign or inconsistent originals fail.

The primary obtains original PNGs for normal play/Sit/override and completed
cancel/wait checkpoints. Baseline, cleanup, open, close and background use new
native sources. The actor uses its own native sources and obtains its own image
for the final post-override cancel, needed by its background restoration proof.
An actor that missed its original playback cannot borrow the primary's proof.
Each image retains the real consumed-model/draw/configuration/body/marker join.
Changed-image comparison reopens the prior image in the same namespace. Across
namespaces, the common journey still compares the actual public image bytes;
no private index-order exception or invented comparison is introduced.

A new active observation waits for actual native history, at most 32 reads and
three monotonic seconds, using 75 ms gaps. Only an absent native call, loading
or a short measured interval is pending. Actual caller, selected source,
requested resource, generation and native continuation must match the real
ordinary input. At least three loaded frames must span the common required
150..500 ms before effect/image acquisition. The ordinary proof still rejects
frozen poses, wrong consumed bytes, missing generations and foreign calls.
No input is retried. Short-clip throughput still requires actual device
qualification; synthetic timing is not a performance or acceptance result.

`PhoneEmoteEffects.pending_restore(reference, played)` has its own closed
`{emotePendingRestoreVersion:1,role,runId,binding,call,frame,played,state,proof}`
packet. For handled cancel/wait actions whose own original native generation
is still playing, the role reports that actual active state without a completion
image. Once the real restore is observed, ordinary restoration and image checks
apply. A consumed cancel or natural delay never becomes an invented idle or
early-cancel success. This helper can also reconstruct historical originals;
only the enclosing current role acquisition applies delivery freshness.

## Exact motion file ownership

`PhoneEmoteMotionFiles` reuses the Graphics/Emote exclusive private file engine,
with its own 2 MiB bound. `write(ticket,capture,raw)` takes exactly
`{call,state,capturedEpochMs,requestId,bytes,sha256}` plus actual common motion v1
JSON bytes. Captured epoch and request ID must be the original after-source
host epoch and native request ID. The file descriptor has exactly
`{emoteMotionFileVersion:1,binding,runId,role,stage,ticket,call,state,capturedEpochMs,requestId,name,bytes,sha256,phase,file}`.
Stage is the durable role sequence, 1..1024. Name is
`emote-motion-<run>-<role>-<stage>-<requestId>.json`. File is null while planned,
then the actual `{device,inode}`. Bytes/digest, role, call, actual after-frame,
ordinary input's native barrier and measured state are checked together.

Planned responsibility precedes exclusive creation. Opened identity precedes
writing bytes; fsync and original-byte validation precede saved. Files must be
private regular single-link files with the recorded actual inode/device. Symlink,
hardlink, replacement, exposed permissions, missing file or corrupt content
cannot inherit a prior proof. Existing files are never overwritten or adopted.
`read` and `archive` return verified original bytes only; `absent` independently
checks absence and never treats an empty/missing file as successful evidence.
Historical archive validation preserves all epochs and acquires no target data.

## Deadlines, interrupted transfers and remaining integration

A complete role read has a 20-second monotonic ceiling. Original/file/image
suboperations retain their existing five-second ceilings. Before returning,
actual fixture ticket, native/host clocks and elapsed monotonic time must still
qualify the original sources and artifact epochs within 1.5 seconds. Slow replay
or delivery cannot redate retained measurements. Namespace rollover requires
an already committed two-role lease; it resets local index/play comparison only,
not the durable public sequence or original history.

`recover()` handles a retained complete observation after an interrupted original,
manifest, scope transfer or final parent commit. It reopens actual saved bytes,
finishes the existing manifest and, if necessary, transfers the exact remaining
completed scope before committing the same durable sequence. It performs no
input/source acquisition and returns no public measurement. An opened original
can advance only after its complete exact bytes validate. Missing/partial files
or unowned manifest files remain errors and retain responsibility. New public
results always require a later `read` with new measurements.

Acquiring failures and incomplete image scopes remain owned for the enclosing
failure-retirement protocol. This component does not delete evidence, role,
admission, source/input, namespace, parent or resource journals. Cleanup samples
here establish only actual current native/UI facts after Run resource restoration;
they cannot replace both independent Lifetime quiet windows or full retirement.
The internal actor `publication()` builds only its own newly measured projection,
original epoch and sequence. Its enclosing owner must post through the separate
actor client after releasing the source lock. A failed POST cannot authorize
re-emitting that old packet; the next publication acquires a new sequence. Separately
credentialed process configuration, scheduling, run retirement and public facade
registration remain to be integrated before a complete Emote capability is
advertised. The generic cleanup must continue to reject retained Emote owners.

Host tests compose real checked admission/source/input/role/image/motion owners
over independent synthetic boundaries. View/Scene completion is explicitly
doubled in these orchestration tests; their real native proof internals have
separate checks. Counterexamples include ignored inputs, forged public resources
or artifacts, duplicate native frames, stale delivery, lost original/manifest/
parent commits, missing originals and corrupt/foreign/replaced motion files.
Controlled loopback tests also use the real fixture HTTP server and distinct
reader/actor credentials: only actor publication succeeds, duplicate packets
fail and a failed reader POST cannot cause cached re-emission. They qualify
test/adapter logic only, not product features or devices.


## Failed role transfer, archive version 1

`transfer_failed(retain, retained=None)` is allowed only under the actual held
source lock, Run cleaning-inputs state and real cleanup activation. Source
failures must already be transferred. It retains the exact acquiring/retaining
role control and uses the existing completed/failed Observation transfer plus
Capture cleanup. It sends no play, input retry, new image or effect measurement.
The role returns to ready only after verified retention, with the successful
public sequence, local index and original successful manifest prefix unchanged.
A failed attempt cannot become a public observation or an actor sample.

The exact packet is
`{emoteRoleFailureArchiveVersion:1,segment,header,inputHeader,inputSourceHeader,sourceHeader,scope,originalDiagnostic,manifestDiagnostic,motionDiagnostic,cleanup}`.
The three input/source headers freeze the actual historical context. Header is
the original failed role journal. Its actual scope ID, index, ticket, image policy,
run/candidate/process binding and Source admission policy remain mandatory.
Cleanup is the original real phase snapshot; exact birth and activation history
must agree when a retained packet is reused.

Scope is null before a scope ID was allocated. Otherwise it is exactly
`{kind,archive}`. Kind complete carries the existing complete Observation archive;
kind failed carries its original failure archive and actual child retirement.
Kind absent is permitted only for acquiring state with no role original,
manifest or motion intent, after independently observing absent scope/capture
host metadata and world-owner metadata. It classifies host ownership only and
contains no native retirement proof. Final native resource/receipt/quiet checks
remain mandatory. Missing metadata cannot replace a required complete archive.

The existing original diagnostic preserves planned absence, exact opened-file
bytes/identity/times or a verified saved role original. A manifest diagnostic is
null or `{present:boolean}`; only a planned index may be absent. Saved originals
recompute their effect/image/motion proof; saved index entries must preserve the
exact previous prefix and pending original. Successful historical files remain
byte/inode/digest checked, while restoration's referenced last/play/image
observations are independently replayed. They are retained historical data,
not fresh results or a new verification of the whole journey.

`PhoneEmoteMotionFiles.diagnostic` introduces the closed partial descriptor
`{emoteMotionDiagnosticVersion:1,name,bytes,sha256,file}`; file is exactly
`{device,inode,modifiedNs,changedNs}`. It reads actual private, single-link,
recorded-identity bytes under the existing 2 MiB/five-second bound. Planned files
must be absent, saved files must reopen as valid original native motion, and
opened files retain their actual partial bytes without parsing/completing a
measurement. A saved motion file must additionally match this scope's original
after-frame and measured state. Empty, changed, foreign or replaced bytes never
supply success. Existing bytes and epochs are not rewritten.

Retention precedes scope metadata removal. Actual GPU-buffer/receipt retirement
is verified by the existing Capture/world owners; an ignored release keeps the
role, scope and native ownership open. Lost original/index/final-role writes can
be transferred as failures, including a complete scope already removed after a
saved role original. A retained failure packet can finish the same interrupted
transfer without another capture or replacement epoch. Rejected/lost retention,
phase changes, stale ownership, partial-file mutation and ignored commits remain
errors. Whole-operation bounds remain 20 seconds with existing five-second child
limits. `failure_archive` is historical replay only and returns no new facts.

Failure-owner/record version 3 integrates this path for both roles after source
failure recovery and before admission/input restoration. Versions 1/2 remain
readable, preserving their old source/admission record bytes and original inodes.
Role journals and all diagnostic originals still require final whole-run
retirement; an independently measured cleanup observation requires a later new
source read after actual resource restoration. Host tests qualify logic only.

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

Failure-owner/record versions 3/4/5/6 integrate this path for both roles after source
failure recovery and before admission/input restoration. Versions 1/2 remain
readable, preserving their old source/admission record bytes and original inodes.
Role journals and all diagnostic originals still require final whole-run
retirement; an independently measured cleanup observation requires a later new
source read after actual resource restoration. Host tests qualify logic only.


## Obsolete actor reads before image allocation, version 1

An independent actor can finish a Source acquisition while the controlled fixture
advances its actual ticket. Source already retains the real before/after phases
and returns `EmotePhaseChanged`; the Role's acquiring intent must also remain
accounted for. `transfer_phase(retain, retained=None)` transfers that obsolete
host attempt without waiting for cleanup and without acquiring a replacement
measurement. It applies only to the actor, acquiring state, image=false and
null scopeId/motion/original/manifest. The actual source must be ready after its
original acquisition/transfer. No already allocated image/capture scope can use
this operation; it remains subject to full resource cleanup.

The closed original packet is exactly
`{emoteRolePhaseRetirementVersion:1,segment,header,inputHeader,inputSourceHeader,sourceHeader,scope,originalDiagnostic,manifestDiagnostic,motionDiagnostic,phase}`.
The three original input/source headers and original role header retain their
actual run/candidate/process, role, namespace, root and image-policy identities.
Scope and all diagnostics must be null for this path. All historical successful
role originals and referenced play/image records are reopened, unchanged.
Phase is original actual provider metadata. It must prove that the pending
ticket occurs in the retained activation history and is no longer current;
a same-phase failure cannot be relabelled obsolete. This packet supplies no
public sample, PNG/motion file, native release receipt, idle or quiet verdict.

Before and after retention the helper independently checks that this role has
no observation/capture metadata and no world-render ownership. An unknown child
or world owner blocks transfer even when the parent says image=false. The
mandatory callback must durably retain the exact packet before pending can be
cleared. A later provider phase may extend the same original birth/history, but
cannot reactivate the retired ticket or replace its original timestamps. The
whole operation, including repeated validation and callback, takes at most five
seconds. Rejected/slow callbacks and ignored commits keep ownership. An exact
already-retained packet can recover a lost callback or final clear without
another native/image/input query or an incremented successful role sequence.

`phase_archive(packet)` performs historical validation only. It returns the
unchanged packet, never a usable live owner or fresh product facts. Existing
role header/record formats stay at version 1 and cleanup failure archives keep
their existing version 1 format and cleanup requirement.

Failure-owner/record version 5 adds kind phase. `collect_phase()` explicitly
collects the current actor's obsolete, resource-free attempt under the loaded
Run/source lock, including prepared/active normal operation. It validates that
classification and exact current namespace before writing a new enclosing intent.
The enclosing actor must finish obsolete-attempt retention before acknowledging
a namespace freeze or letting the parent advance that namespace. A new namespace
cannot adopt the old attempt; existing frozen proof and pending ownership are
never relabelled. Unclassifiable image
attempts and same-phase failures cannot leave a new phase-transfer intent.
Old pending/completed failure formats 1..4 remain readable; existing original
bytes and indexes are unchanged. A pending phase transfer may finish during
later real cleanup, retaining its old phase packet. Ordinary cleanup still
collects normal source/role/lifetime/admission failures through their original
cleanup-only paths. Whole resource/file/journal retirement, the independent
actor loop and public Emote facade remain required before registration.

Host counterexamples use a real Source acquisition whose producer advances the
actual controlled fixture between its phase reads. Tests cover exact original
retention, subsequent actual normal input and new actor measurement, lost parent
completion and all staged original/index writes, late cleanup, unknown image/
world owners, forged image intents, same-phase errors, altered/foreign packets
and rejected/slow/ignored retention. They qualify orchestration only; native
code is uncompiled and no device behavior is accepted.


## Obsolete actor image retirement, version 2

New `transfer_phase(retain, retained=None, archive_version=None)` calls write
`emoteRolePhaseRetirementVersion:2`. The closed field set is unchanged from v1;
version 2 also admits acquiring/retaining actor image attempts and their actual
Scope/original/index/motion diagnostics. Run must already exist, the source must
be ready with no pending read, and the actual role namespace must match the
current source. `phase_intent()` checks this classification and the retired
ticket against a new original phase, anchored to an independently reopened
source/provider history, before the enclosing failure owner writes an intent.
A reconstructed phase reader cannot adopt a replacement provider birth.

The existing ordinary cleanup transfer and phase transfer share the same child
retirement implementation. Ordinary cleanup still requires Run cleaning-inputs
and an actual cleanup stimulus. Phase transfer instead requires the actor's old
ticket to occur before the current ticket in the actual immutable fixture
activation history. This authorizes retirement of that exact obsolete E2E
measurement only; it sends no ordinary close, cancel, playback or OS input and
provides no product cleanup/idle/quiet result.

Scope complete carries the original complete Observation archive, including its
actual GPU-buffer and issuer-receipt retirement. Scope failed carries the actual
Observation failure archive, child Capture retirement and any partial PNG/
original/index evidence. The existing Capture cleanup independently observes
memory/receipt absence and retains its exact release proof before metadata
removal. An ignored release keeps Role/Observation/Capture/world ownership.
Missing metadata alone cannot replace a required child retirement packet. Scope
absent retains only the existing unmaterialized host-ownership classification;
it supplies no native release proof or whole-run verdict. With no scopeId,
independent absence of this role's scope/capture/world owners is mandatory.

Successful role sequences, indexes, lastImage and played references are unchanged
by failure transfer. A completed image whose enclosing role original/index or
final commit was interrupted stays a failed attempt; it cannot be published as
new actor evidence or substitute for a successful prior cancel image. Original
completed Scope data, actual native/image observations and partial file bytes
remain available in the exact transferred archive. New public state requires a
later fresh role acquisition.

The mandatory callback durably retains the full original packet before child
metadata and then pending role ownership can disappear. The original file engine
retains its existing 1 MiB limit; the packed control remains at 64 KiB. The full
operation is bounded to 20 seconds, with the existing five-second child and file
bounds. Rejected/slow callbacks and lost/ignored commits preserve responsibility.
A retained packet can finish the same staged original/index/child/parent transfer
without another acquisition, input, image or successful sequence. Later real
cleanup may extend the same provider history; it never replaces old epochs.

Version 1 remains readable and recoverable through `archive_version=1`, retaining
its original resource-free grammar and five-second bound. Boolean/unknown version
selectors are rejected. Failure-owner/record version 6 writes new v2 phase
archives; pending record v5 continues its exact old v1 archive and original bytes/
inode/digest. A v5 record cannot carry a v2 image archive. Other failure archive
formats and role control/record versions are unchanged. Whole native/resource/
file/control retirement, the actor loop and complete feature facade remain open.

Host checks drive actual normal Sit -> Crying override -> cancel and this actor's
own native observations. The synthetic GPU producer can advance the real fixture
phase during acquisition; its real buffer/receipt owners still have to retire.
Cases include ignored release, complete/partial image-role records, all staged
failure-original/index writes, lost parent completion, same-phase denial,
changed/foreign native retirement, old v5 recovery, changed provider birth and
strict version selection. These confirm Python logic only, not compiled native
code, device behavior or a complete common Emote journey.

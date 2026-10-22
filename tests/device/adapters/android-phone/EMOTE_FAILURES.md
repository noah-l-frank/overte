# Phone Emote source/admission/role/work retention, version 4

`PhoneEmoteFailures` connects actual failed readonly Source acquisitions and
admitted/failed Admission contexts, interrupted role/image/motion attempts and
interrupted lifetime work reads to the existing Run input-cleanup path. It is an internal component. No failed attempt
becomes a source sample, no evidence file is deleted, and no complete Emote
capability is registered. Three Phone feature triples remain source-implemented;
native code remains uncompiled and all device behavior untested.

## Failed source archive

`PhoneEmoteSources.transfer_failed(retain, retained=None)` requires the actual
current cleanup activation under the held source lock. It accepts an existing
reading owner or the exact already-transferred ready owner with its original
retained proof. It acquires only fixture input metadata, no native/UI source,
input, image or product state. The five-second deadline includes original file
inspection, retention, repeated verification and commit.

Its exact original packet is
`{emoteSourceFailureArchiveVersion:1,segment,header,predecessorHeader,originalDiagnostic,manifestDiagnostic,cleanup}`.
Header is the unchanged source v3/v4 reading journal. Segment is 0..15;
predecessorHeader is null in namespace zero, otherwise its actual prior source
header. Historical replay checks both roles' identity, candidate/process binding,
source policy, native/UI/Script/phase continuity and namespace predecessor.
Cleanup is the actual original phase snapshot; its stimulus must be cleanup.
The real current fixture must still have the same run birth and activation
history when a retained proof is reused. A new cleanup ticket cannot adopt it.

`originalDiagnostic` is null for an absent acquisition result, a planned file
independently observed absent, or a fully verified saved original. An opened
file uses the existing diagnostic descriptor with actual name, size, digest,
inode/device and stable modification/change times. Saved originals additionally
reconstruct their actual native/UI/Script/history proof. None of these branches
turns an incomplete file into a native measurement.

`manifestDiagnostic` is null when no manifest was planned; otherwise it is exactly
`{present:boolean}`. Absence is permitted only for a planned manifest. Existing
files must be private, regular, single-link JSON with the exact owned digest,
index, original and prior entries. Missing saved files, changed bytes, replacement
inodes, links, exposed permissions and foreign contexts fail closed.

Retention must complete before pending is cleared. The callback receives the
exact frozen packet; the component then reopens the same actual files, checks
actual cleanup again and persists ready with the unchanged frame prefix and
revision. It adds no frame and returns only the failure archive. A later source
measurement requires a new acquisition. Rejected/lost retention, a phase change,
slow verification or an ignored commit preserves responsibility. Reusing an
original retained packet never replaces its timestamps or fixture nonce.

`failure_archive(packet)` is historical validation only. It reopens original
files and reconstructs the old reading context without target/fixture queries,
a usable live owner or a fresh verdict. It remains valid after subsequent source
frames only while its original evidence files remain intact.

## Durable enclosing failure owner, versions 1, 2, 3 and 4

Construct `PhoneEmoteFailures(run)` under the loaded Run's held source lock. The
actual candidate/process binding, run, fixture and artifact root must agree.
`collect_sources()` is allowed only in Run's cleaning-inputs phase. It first
recovers any exact pending failure transfer, then inspects the current primary
and actor source journals. A missing source journal is not created. A source
without a failed read adds no failure record or owner file.

`collect(source, kind="source")` accepts only the current actual namespace and
same lock/binding. Kind admission uses namespace zero and its actual Admission
owner. `collect_admissions()` runs after source failure transfer, before ordinary
input restoration, for both roles' existing admission journals.
It persists responsibility before source transfer. The private control is exactly
`{emoteFailureOwnerVersion:4,runId,fixtureUrl,binding,artifactRoot,payload}`. Its
existing bounded packed payload holds one `{count,manifests,pending}` state.
Count is 0..1024; manifests retain the existing 128-entry blocks and eight-block
bound. Pending is null or
`{kind,recordVersion,role,segment,headerSha256,archive,original,manifest}`.
Kind is source, admission, role or lifetime. RecordVersion is 4 for new transfers; a recovered v1
source transfer retains record version 1. Header SHA-256 binds the
exact source or admission journal. Archive is null until the actual complete failure
packet is durably frozen; it contains no guessed product effects. Original and
manifest use the existing planned/opened/saved storage protocol.

The same 64 KiB control and 1 MiB original limits apply; neither is increased.
A failure original is exactly
`{emoteFailureRecordVersion:4,index,kind,archive}` and uses the existing
immutable file/index engine with kind source-failures and primary run ownership.
An actor's failure archive still names and validates the actor's actual original
source stream. Primary ownership of diagnostic storage supplies no actor facts.
Each original reopens its actual source failure or admission proof before
retention succeeds. An approved primary admission must match the original
parent-pinned hash. A failed pre-setup admission remains unapproved. The fixed
legacy source-failures storage kind is retained for both record types; no
original filenames or indexes are renamed.

Version 1/2/3 owner and record files remain readable. Version 1 pending sources
retain record 1; version 2 pending source/admission transfers retain record 2. Reconstruction alone never
rewrites a v1 control. Its pending transfer is interpreted as source/record 1;
the next explicit transition writes owner v4 while preserving its frozen v1
record bytes, digest, inode, manifest and epochs. Version 1 cannot encode the
new kind/recordVersion fields or an admission record.

Run cleanup recovers owned foreground first and reconciles any committed
namespace transition, then collects failed sources and retires admission owners
with interrupted roles and lifetime work in between, before releasing namespace freezes and invoking ordinary input restoration. A lost final failure-owner
commit can reuse the exact already-transferred source, original and manifest;
it cannot append a second record or advance native/UI sequences. Failure journals
and their evidence remain owned for final whole-run retention/retirement.
General cleanup must continue to reject a remaining Emote owner.

## Interrupted archive-file writes

The existing original store adds two explicit host-only recovery operations.
`resume_write(index, record, original_intent)` accepts an independently validated,
frozen archival record with exactly the intended bytes/digest/index/context.
A planned file must be absent and is created exclusively; its actual inode is
persisted before writing. An opened file must have the recorded actual identity
and a byte prefix of that exact frozen record. Only the missing suffix is appended;
existing bytes are never overwritten or truncated. A saved original must reopen
unchanged. Foreign prefixes, matching bytes in a foreign inode, unowned existing
planned files, missing saved files, links and invalid permissions are errors.
No native fact is completed from expected state.

`resume_manifest(references, original, manifest_intent)` finishes only its exact
durable intent. It reconstructs the canonical index from the verified original
and existing prefix, compares its entire reference/digest, then either verifies
the existing file or creates a missing planned file with compare-and-swap.
A missing saved index is not recreated. Only then may its saved callback finish.
All source/original formats remain unchanged. Both operations retain their
existing five-second budgets and private file limits.

## Boundaries still required

This owner integrates failed readonly Source reads and original Admission
retirement, including a failed cache check before View/Scene setup, plus the
[failed role/scope transfer](EMOTE_ROLE.md#failed-role-transfer-archive-version-1). Full cleanup
when initial admission fails before the first baseline, missing View/Scene setup,
selected native work,
scene/view/namespace/background resources, independently credentialed actor
retirement and final evidence/control-journal retirement remain obligations of
the complete facade. No resources-restored, quiet, cleaned or successful feature
result is inferred from failure retention. A failed journey remains failed.

Host checks compose the real Run, checked Sources, failure owner, original files
and indexes over synthetic native/Qt/probe sources. Setup completion boundaries
are explicitly doubled; devices are never contacted. Counterexamples include
both roles' absent/partial/saved source results, lost/rejected retention, mutation
or replacement during transfer, changed phase, late verification, ignored commits,
foreign archived contexts and interrupted original/index/final-owner writes.
They verify ownership/test logic only, not product behavior or acceptance.


## Role/scope ownership in version 3

`collect_roles()` recovers pending transfers, inspects both existing role
controls and retains acquiring/retaining attempts through the actual Role
failure operation. Run order is source failures, role/scope failures, lifetime failures, Admission
retirement, namespace/input restoration. Scope/capture cleanup keeps its existing
original byte, native buffer and issuer-receipt proofs. A failed cleanup release
never permits a role reset. The role's successful sequence and manifest prefix
remain unchanged; new cleanup data requires a later fresh observation.

Records of kind role use the original role-failure archive v1, including its
image policy, exact source/input context and partial original/index/motion
metadata. The same control/original/file/time limits apply. A complete image
whose role write failed is retained as failed ownership; its old public result
cannot be emitted or published as a new sample. An absent unmaterialized host
scope contains no native retirement proof. Whole native and host retirement
still has to be verified before full feature registration.

Old completed and pending v1/v2 records are not rewritten. V2 pending admission
records retain their original bytes/digest/inode during explicit owner upgrade.
Versions 3/4 admit kind role; only version 4 admits kind lifetime. Source and Admission packet formats remain
unchanged; the new role archive and partial-motion descriptor have their own
version 1 contracts in the registry.


## Interrupted lifetime work in version 4

`collect_lifetimes()` validates both existing role lifetime controls, including
ready/complete controls whose unknown versions must never be skipped. A reading
control is transferred through `PhoneEmoteLifetime.transfer_failed`. Source
failures are resolved first; a pending source cannot be interpreted as a ready
lifetime original. Actual original worker/source packets already completed in
the lifetime journal remain unchanged. The lost attempt never adds a worker
packet, source frame, successful sequence or quiet/idle verdict.

The exact failure packet is
`{emoteLifetimeFailureArchiveVersion:1,segment,header,sourceHeader,cleanup}`.
Header is the original reading lifetime control, sourceHeader is that role's
actual ready source control after source failure transfer, and cleanup is the
original actual provider phase. The actual namespace, role, admission policy,
run/candidate/process, private root and complete provider birth/history must
match. Historical worker records and their source references are independently
reopened. The pending afterRevision/index must agree with that original context.
No unknown raw native response is promoted to a completed worker packet.

The mandatory callback retains this original packet before the lifetime journal
can return to ready. Only its pending intent and unavailable window are cleared;
all completed original records remain, with their actual epochs/cursors. Rejected,
slow or lost callbacks, changed cleanup, ignored writes or altered original
files preserve ownership. An exact retained proof can finish a lost final clear
or enclosing completion without another source/work/input query or duplicate
failure original. Historical replay through `failure_archive(packet, source)`
returns reading state only. Only a later actual new source/work acquisition can
complete a quiet window. Existing 40-record/30-second lifetime and five-second
transfer bounds remain unchanged; this path does not reset an exhausted window.

Version 4 retains old pending record versions and old completed bytes/inodes/
digests. New original and manifest writes use the existing exclusive staged
engine; planned/opened/saved interruptions resume only exact owned bytes. The
same 64 KiB control and 1 MiB original limits apply. These journals and originals
still require whole-run transfer/retirement. Source implementations are tested
with synthetic host producers only; no native build or device acceptance is
implied.

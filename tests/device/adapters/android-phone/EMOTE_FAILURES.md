# Phone Emote failed source retention, version 1

`PhoneEmoteFailures` connects actual failed readonly Source acquisitions to the
existing Run input-cleanup path. It is an internal component. No failed attempt
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

## Durable enclosing failure owner

Construct `PhoneEmoteFailures(run)` under the loaded Run's held source lock. The
actual candidate/process binding, run, fixture and artifact root must agree.
`collect_sources()` is allowed only in Run's cleaning-inputs phase. It first
recovers any exact pending failure transfer, then inspects the current primary
and actor source journals. A missing source journal is not created. A source
without a failed read adds no failure record or owner file.

`collect(source)` accepts only the current actual namespace and same lock/binding.
It persists responsibility before source transfer. The private control is exactly
`{emoteFailureOwnerVersion:1,runId,fixtureUrl,binding,artifactRoot,payload}`. Its
existing bounded packed payload holds one `{count,manifests,pending}` state.
Count is 0..1024; manifests retain the existing 128-entry blocks and eight-block
bound. Pending is null or
`{role,segment,headerSha256,archive,original,manifest}`. Header SHA-256 binds the
exact failed source journal. Archive is null until the actual complete failure
packet is durably frozen; it contains no guessed product effects. Original and
manifest use the existing planned/opened/saved storage protocol.

The same 64 KiB control and 1 MiB original limits apply; neither is increased.
A failure original is exactly
`{emoteFailureRecordVersion:1,index,kind:"source",archive}` and uses the existing
immutable file/index engine with kind source-failures and primary run ownership.
An actor's failure archive still names and validates the actor's actual original
source stream. Primary ownership of diagnostic storage supplies no actor facts.
Each original reopens its actual source failure proof before retention succeeds.

Run cleanup recovers owned foreground first and reconciles any committed
namespace transition, then collects failed sources before releasing namespace
freezes and invoking ordinary input restoration. A lost final failure-owner
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

This owner currently integrates failed readonly Source reads only. Failed
admission before setup, incomplete role/image/motion scopes, selected native work,
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

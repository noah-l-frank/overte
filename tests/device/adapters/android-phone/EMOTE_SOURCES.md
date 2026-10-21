# Phone original Emote source acquisition, versions 3 and 4

`overte_phone_emote_sources.PhoneEmoteSources` connects the original Emote
measurement join to actual guarded Phone source factories. The owning caller
must already hold the existing `phone-script-sources.lock`, use an existing
candidate-bound session and supply a `PhaseFixtureReader` for its owned Emote
run and an explicit existing private `artifact_root`. Each role has its own `phone-emote-<role>-sources.json`; primary and actor
never copy one another's packets. This component advertises no complete Emote
capability. Phone remains at three complete areas, with native instrumentation
uncompiled and all devices untested.

## Exact stored contract

The private versioned header has `emoteSourcesVersion:3`, `runId`, `fixtureUrl`,
`role`, full actual `binding`, actual `artifactRoot` and bounded compressed `payload`. The binding is
the existing source revision, installed artifact digest, PID/start, SDK session,
generation and target fingerprint. Payload contains one exact record:
`phase`, `revision`, immutable original `manifests` and `pending` or null.
The phase is `ready` or `reading`; revision equals the original frame count,
bounded to 1,024. Existing private-file ownership, symlink, permissions, atomic
write, size and digest checks apply. No output includes a target selector.

Originals live in the [bounded immutable frame store](EMOTE_ORIGINALS.md).
At most eight index references cover 128 original descriptors each. Complete
original frame bytes remain private files; the active owner stays below the
existing 64 KiB limit. Global metadata/security limits are unchanged. A reading
record's exact pending fields are `startedEpochMs`, `role`, `revision`, `original`
and `manifest`. Planned/opened/saved original-file identity and planned/saved
manifest intent are persisted before the corresponding writes. Interrupted
writes remain responsibilities and cannot be reset by the same live object.

A frame has exactly `group`, `ui`, `widgets`, `phaseBefore`, `phaseAfter`,
`hostEpochMs` and `epochMs`. Group is the four-original root/Script/Rig/root
contract in [Emote Rig measurements](../../native/EMOTE_RIG_MEASUREMENTS.md).
`widgets` retains the original nonce-bound native Qt result. `ui` retains that
result's exact controls/scope plus actual separately acquired SDK tablet
visibility. Host and device clocks remain separate and are never substituted
for original packet timestamps. Phase originals contain input metadata only;
neither peer facts nor runner expectations enter the product observation.

## Acquisition and replay

`read()` uses only existing read-only factories: configured Script roots,
submitted Script observations, native feature observations and original Emote
widgets. It persists `reading` responsibility before dispatching any query.
It reads original fixture phase, root, Script, a later actual Rig evaluation,
root, widgets/visibility and fixture phase again, in that order. Native Script
reads require actual complete effects/load/membership/code sources. Returned
frames expose no feature state, effect verdict, peer publication or resource
cleanup claim. Ordinary input is refused by every supplied transport.

All complete packets and their cross-source ordering are revalidated. The
five-second whole-acquisition deadline includes persistence and guards; actual
delivery must additionally fit the existing 1.5-second source freshness window.
Independent monotonic elapsed-time floors cover sequential acquisition and the
final durable write even when external clocks do not advance. The device-clock
age floor starts at its actual independently read acquisition barrier; earlier
historical replay cannot retime or artificially age later native packets. The
five-second overall read deadline still includes that replay. Failed fresh
delivery can retain complete originals as historical evidence, never retimed
current facts.

Reconstruction replays every original Script transition using the existing
reader's original packet validator and pure prefix/retirement transitions,
including histories beyond its ordinary 512-frame batch API. It revalidates
original root/manager/code, native/Rig/history continuity,
immutable fixture prefixes and original widget counters, and pins the unchanged
source profile. The next live read restores all actual floors, including Rig
evaluation and native callback histories, then obtains new nonces/counters and
fresh original packets. Unfinished `reading` responsibility cannot be reset by
constructing another object. There is no API for deleting it or reporting empty
cleanup success.

A fully qualified acquisition crossed by a new active fixture ticket is saved
under both original phase packets and raises `EmotePhaseChanged`. Its data cannot
be relabeled or published as the new phase. A subsequent read must acquire all
new originals. Malformed/foreign evidence, retired fixtures, changed bindings,
manager replacement and lost results fail instead of entering that race path.

## Remaining whole-feature work

The complete owner must join durable ordinary input intent and pre-input native
barriers to these independently read frames, then compose measured state using
the [Rig contract](../../native/EMOTE_RIG_MEASUREMENTS.md). It still needs the
controlled avatar scene, original avatar pixels and challenge, independent actor
publisher, background-resume proof, actual owned timer/callback absence, quiet
cleanup windows and digest-scoped host-journal retirement. These requirements
cannot be replaced by a valid source transcript. No native build or physical
qualification has run.

Version 1 was a local unadvertised component with no device qualification or
required platform producer. Version 3 rejects and preserves v1 journals; there
is no automatic conversion, deletion or empty-state replacement. Preserve old
originals for their offline v1 reader and verify actual cleanup before using a
fresh run. A pending v1 record never becomes v2 current evidence.

Earlier v1 verification: the shared 1,217-case no-build baseline and the 856-case Android
Phone host regression passed with no failures, errors, skips or compiler
attempts. After the final qrc-resource/actual-Rig-cursor hardening, all 78 affected
source, Rig, root, profile, history, Phone transport and probe cases passed.
These runs verify host logic and synthetic boundaries exclusively.

Version 3 requires native animation history 2 and original VM-to-native caller
provenance. All original native histories replay their caller cursors across
immutable files, including ring trimming. Earlier source journals are preserved
and rejected rather than migrated or adopted. The input journal remains version
2 and can only reconstruct against this exact live source owner.

General Phone teardown always attempts base cleanup, but returns unavailable
while either role's source journal or the input journal remains. It does not
forget originals or infer retirement from process shutdown.


## Checked world and all-executable sources, version 4

The current run owner supplies the explicit [admission policy](EMOTE_ADMISSION.md)
through `PhoneEmoteSources(...,admission=policy)`. Version 4 adds exactly
`admissionPolicy` to the version 3 outer header and exactly `probe` to every
original frame. It independently reads the existing original `probe.snapshot`
inside the bound existing input session, before the final fixture phase/clock
checks. Every frame verifies current actual domain UUID/host/port/markers, original
probe freshness and all manager/submitted/compiled/require identities against the
fixed executable catalog. The probe and compiled pinned probe manager belong to
the same guarded current candidate/process. Original sample epochs/sequences are
retained; repeated sequences require identical originals. Expected world values
are comparison inputs and are never returned as a measured snapshot.

Version 3 remains its exact old unchecked format for legacy component/cleanup
use. A checked header or namespace cannot downgrade, an unchecked predecessor
cannot silently become checked, and successors inherit the actual prior checked
policy when no explicit argument is supplied. The current run always supplies
its parent-pinned policy for new sources. Private in-memory policy removal or a
changed actual control header fails before acquisition. Historical replay validates
its own original format and cannot substitute version 3 frames for a version 4
role/effect/image archive. Primary/actor joins require equal admission policies.
Source/input/observation bounds, source epochs, native commands and common journey
version 17 remain unchanged. Full Emote capability registration is still pending.


## Completed interrupted acquisition recovery

`recover_complete()` is an internal, explicit recovery operation under the
existing held source lock. It reads no target/UI/fixture source, dispatches no
input and returns no fresh measurement. Its actual prior control must still
be reading, with an opened or saved original containing the complete exact
owned bytes. It independently validates that original frame, checked admission
policy, source/native/UI/phase continuity, compiled Script history and native
animation history. An actual namespace predecessor remains bound throughout.

Only after validation can an opened original advance to saved. The existing
manifest must either be absent from the pending metadata (so the normal durable
append owns its creation), or already exist with exactly the pending reference,
original and previous entries. A planned manifest with verified complete bytes
can finish its saved callback; an absent planned file is not adopted or invented.
The method commits the same original revision and restores historical cursors.
A subsequent public measurement still requires a new ordinary source read with
new actual native/UI/phase observations. Original epochs are never replaced.

Missing results, an empty/partial file, changed bytes, a missing saved file,
foreign context or late verification remain errors. They keep reading state and
all existing ownership for the enclosing failure-retirement protocol. This
method cannot erase pending responsibility, close a run, claim native quietness
or qualify product behavior. Its five-second bound includes original validation,
manifest persistence and final parent commit. Formats remain versions 3/4.

Host counterexamples cover saved original/manifest callback loss, a complete
opened file after lost verification, absent/partial/changed originals, late
replay and checked version 4 recovery without policy downgrade or redating.
They acquire no replacement sources and do not qualify devices.

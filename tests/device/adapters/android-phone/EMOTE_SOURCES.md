# Phone original Emote source acquisition, version 2

`overte_phone_emote_sources.PhoneEmoteSources` connects the original Emote
measurement join to actual guarded Phone source factories. The owning caller
must already hold the existing `phone-script-sources.lock`, use an existing
candidate-bound session and supply a `PhaseFixtureReader` for its owned Emote
run and an explicit existing private `artifact_root`. Each role has its own `phone-emote-<role>-sources.json`; primary and actor
never copy one another's packets. This component advertises no complete Emote
capability. Phone remains at three complete areas, with native instrumentation
uncompiled and all devices untested.

## Exact stored contract

The private versioned header has `emoteSourcesVersion:2`, `runId`, `fixtureUrl`,
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
required platform producer. Version 2 rejects and preserves v1 journals; there
is no automatic conversion, deletion or empty-state replacement. Preserve old
originals for their offline v1 reader and verify actual cleanup before using a
fresh run. A pending v1 record never becomes v2 current evidence.

Earlier v1 verification: the shared 1,217-case no-build baseline and the 856-case Android
Phone host regression passed with no failures, errors, skips or compiler
attempts. After the final qrc-resource/actual-Rig-cursor hardening, all 78 affected
source, Rig, root, profile, history, Phone transport and probe cases passed.
These runs verify host logic and synthetic boundaries exclusively.

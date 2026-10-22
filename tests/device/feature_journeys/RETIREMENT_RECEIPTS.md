# Actor resource-retirement receipts

This channel is separate from feature facts and does not change their existing
projections or `PhaseWitnessPublisher`. Only a feature-specific historical
decoder can establish actual native cleanup. A receipt hash, POST acknowledgment,
fixture phase advance or run death does not establish native resource retirement.

The actor uses `PhaseRetirementPublisher(store, binding, phase, lock, guard,
validate_original, epoch_ms=..., monotonic=...)`. Its immutable original callback
for the complete stage must return exactly `{ticket, public, acquisition, retirement}`. `public` is the
complete locally validated cleanup observation with no resources. `retirement`
contains `originalSha256`, measured `quiet` originals, and closed `provenance`.
The full observation stays in the private actor journal. The callback must check
the feature's actual file/listener/VM/callback/timer/GPU/UI lifetimes, original
ownership and repeated quiet evidence before an issued POST is persisted.

Version 2 adds an explicitly separate `avatar-scene-retired` stage, available
only to Avatar. Its callback returns `{ticket, scene, acquisition, retirement}`.
The closed scene summary enumerates entity, file, GPU, marker pixels, Qt UI,
script listener, script VM, timer and world view retirement, with exactly
`account-session` remaining. It has no empty whole-resource claim or feature
facts. The feature decoder must establish those original scene lifetimes before
publication. This stage can order the later ordinary account logouts without
pretending that either account is already retired. Only one scene receipt per
cleanup ticket is allowed, before any complete receipt for that ticket.

`publish(original)` owns one POST; `resolve()` reads only after uncertainty and
never sends that POST again. The private namespaces are separate from ordinary
actor fact publication. Historical `archive` validates original files without
HTTP or a live SDK. Phase/run retirement resolves publication responsibility
only. A missing receipt under the same phase remains unresolved.

`POST /runs/<run>/retirements` is actor-only. Authenticated reader/actor/adapter
GET returns a closed journal containing a complete retirement summary: run, sequence,
original capture time, empty resources and native lifecycle counters. It contains
no feature state, effects, pose/animation facts or image artifacts. Its provenance
reference is exactly `{index, sha256}` and cannot carry an opaque facts payload.
The explicitly labeled Avatar scene stage instead carries its closed `scene`
summary; it cannot carry a `cleanup` summary.
Actual candidate/target/process binding and an exact SDK-session hash accompany
the receipt. The full SDK session identifier remains private.

The receipt also carries the actual source acquisition and four independent
quiet intervals: host epoch/monotonic and native epoch/monotonic. Both boundary
acquisitions are excluded, each interval is at least three seconds, the native
instance/process must agree, and quiet starts after the actual cleanup phase.
The server checks closed grammar, phase, freshness, immutable SHA, original
binding continuity and increasing actor sequence. These publication checks do
not independently validate a renderer or native cleanup.

`PhaseRetirementReader` performs no POST and no actor SDK operation. Its caller
releases the primary source lock before waiting. A caller-supplied historical
admission decoder must validate an actually retained earlier independent actor
binding for this run/phase. Each read joins the exact committed receipt with
original current fixture phases, acquisition freshness and that earlier binding.
Changed/missing actors, stale receipts and phase crossings fail closed.
The reader defaults to `stage='complete'` and refuses a scene receipt. An
Avatar scene reader must explicitly request that stage and retain a separate
private owner. Historical journals enforce the same scene ordering rules.

Contracts `phase-retirement`, `phase-retirement-journal`,
`phase-retirement-publisher`, `phase-retirement-publication-record` and
`phase-retirement-reader` now write version 2 and read versions 1 and 2. Original
version 1 complete bodies, records and reader metadata remain unchanged when
read; they cannot encode a scene stage. `phase-avatar-scene-retirement` writes
and reads version 1. No endpoint, credential right or fact projection changes.
Authenticated loopback tests
exercise Emote, Avatar and Create summaries, once-POST recovery, missing replies,
private full-original reconstruction and the adapter-only information boundary.
Product/native cleanup decoders are modeled in these protocol tests; each whole
feature must additionally test its actual source-to-retirement decoder.


## Optional Web marker scene quiet, version 3

The default complete and Avatar scene writers remain version 2. Their original
wire fields, full cleanup requirements and version-1 historical readers remain
unchanged. Readers also accept version 3. Only explicit
`PhaseRetirementPublisher(..., stage='web-marker-scene-quiet')` on `world-web`
or `emotes` may publish the new scene stage. Its callback returns exactly
`{ticket, scene, acquisition, retirement}`. The closed `scene` contains
`webMarkerSceneQuietVersion: 1`, run/sequence/capture time, `lifecycle`, the exact
ordered `quiet` classes `entity`, `renderer-lease`, `file`, `gpu-sampler`,
`marker-pixels`, `qt-ui`, `script-listener`, `script-vm`, `timer`, `world-view`,
`wk-callback`, and `remaining: ['native-process-resources']`.

This stage is not full native resource retirement. The feature decoder must
retain actual held native resource groups and their original cache surface/root
and renderer-lease identities privately. A native QImage, cached QSG root or WK
holder can remain owned after ordinary scene cleanup. Actual callback/grant
quiet, input endings, Entity/renderer lease ends, file absence and restored pixels
must be validated from their original sources before publication. Neither this
receipt nor its hash establishes those effects independently.

A primary reader must explicitly select this stage. The default complete reader
refuses it; an Avatar scene reader also refuses it. Only one scene stage is
accepted per cleanup ticket, before any complete receipt. A journal containing
an actual version-3 entry writes 3; old journals remain 2. Mixed historical
journals retain original per-entry versions, clocks, binding and ordering.

Final native resource retirement remains a separate feature-owned coordinator:
actual inactive fixture authority, both roles' retained held groups, one normal
Stop intention, each role's own existing-SDK OS/DVT numeric-PID quiet window,
immutable archives and canonical SDK deletion. No post-death zero native
inventory, receipt ACK, phase death or image reset can replace that proof.

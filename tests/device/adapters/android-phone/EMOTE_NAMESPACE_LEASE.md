# Phone Emote primary/actor namespace lease, version 1

`PhoneEmoteNamespaces` coordinates bounded source/input journal rollover through
the existing held source lock. It does not dispatch input, read target native
sources, publish facts or establish whole-run cleanup. The enclosing complete
Emote coordinator and lease retirement remain pending. No full feature
capability is advertised. Native source remains uncompiled; devices are untested.

Construct with a real current `PhoneEmoteSources` for either role. Its actual
run, fixture root, candidate/process binding, private evidence root and lock
bind the lease. The actual path is `phone-emote-namespaces.json` beside the
existing source control files. General Phone cleanup refuses success while it
remains, even after a successful base cleanup ACK.

The closed outer record contains `emoteNamespacesVersion:1`, `runId`,
`fixtureUrl`, `artifactRoot`, `binding`, `payload`. The existing bounded packed
payload contains exactly one `{current,closed,pending}` state. `current` is
0..15; `closed` has exactly that many records, in segment order. Each closed
record has `{segment,call,roles}`. `pending` is null or
`{call,inputsSha256,roles}`; roles are exactly `primary` and `actor`. Pending
acknowledgments may be null; closed records require both. Existing 64 KiB
control and 1,024-frame per-source bounds are unchanged. No journal or original
is dropped, truncated or given a larger limit.

`request(call)` is primary-only and reserves a switch before a new ordinary
`play` or `sit`. The input must be the actual current fixture activation. The
current real primary source must already observe that phase and actual native
inactivity. Its real input owner must be idle/acknowledged with no pending
history transfer; its exact original control digest is frozen. Do not rotate
before `override`, cancel, completion, background or closure: those operations
need the preceding native playback/restoration history in their current input
namespace. The enclosing owner must rotate early enough before new playback to
leave bounded headroom for its continuation and tail cleanup.

Each role independently acquires its own new source frame in the pending phase,
then calls `acknowledge()`. No observed state is supplied to this method. It
reopens the actual source header, all original frames and manifests; cached
object fields cannot replace those files. It requires current source readiness,
no pending read, the actual current input ticket, a host acquisition within
1.5 seconds, inactive native override and no active Emote UI selection. Open
capture/observation control scopes block acknowledgment without adoption or
deletion. The unchanged actual primary input digest is checked again.

Each proof contains exactly `sourcesSha256`, `inputsSha256`,
`sourceIdentitySha256`, `frame`, `nativeInstance`, `rigId`, `historyInstance`,
`callSequence`, `overrideSequence`, `lifecycle`. Header/input hashes come from
actual private control reads. Source identity hashes the independently selected
actual configured/compiled source, not a requested source. `frame` is
`{revision,sha256}` over the reopened original inner frame. Native identities,
call cursors and lifecycle counters come from that original frame. The roles'
source/header/frame references differ; their actual native/source identities,
call cursors, lifecycle and primary input digest must agree.

`assert_acquiring()` must gate every enclosing source acquisition. It rejects an
already acknowledged frozen role and any old segment after advancement. Role
control changes occur under the same source lock; reconstruct the lease after
another role writes rather than reusing a stale compare-and-swap snapshot.

`advance()` is primary-only. It requires both acknowledgments, the actual same
fixture activation, unchanged inputs, no open role scopes, fresh frozen frames
and unchanged actual source control digests. It reopens original source files
and recomputes all saved native/source proof statistics before one atomic lease
commit. Closed source/input control headers are checked on reconstruction and
subsequent lease operations. A late actor, modified source after freezing,
missing original, saved fake statistic, ignored commit or lost return cannot
be treated as a new namespace. A committed transition is recovered by reading
the actual new lease; do not perform a second advance.

The enclosing owner then opens the existing next namespace through
`PhoneEmoteSources(segment=...)`, retaining its immediate inactive predecessor
and existing first-frame/call-cursor continuity checks. It creates a real empty
new input control journal before use; this is no synthetic input ACK. New active
inputs obtain new role-local playback references. Original closed namespaces
and checkpoint artifacts stay owned until verified full retirement. This lease
does not prove browser/GPU/native timer absence or authorize deleting evidence.
Incomplete handshakes remain errors, not successful empty cleanup. The owner
must integrate cleanup-phase recovery and exact retained retirement before
enabling complete Emote capabilities.

Each request/acknowledgment/advance has a five-second monotonic bound, in addition
to the existing source lock, private-file and fixture limits. Host counterexamples
exercise independent originals, stale/foreign phases, cached fake inactivity,
saved fake native statistics, open scopes, missing files, closed-header changes,
ignored/lost commits and slow guards. They qualify test logic only.

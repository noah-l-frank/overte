# Phone Emote primary/actor namespace lease, version 2

`PhoneEmoteNamespaces` coordinates bounded source/input journal rollover through
the existing held source lock. It does not dispatch input, read target native
sources, publish facts or establish whole-run cleanup. The enclosing complete
Emote coordinator and whole-run retirement remain pending. No full feature
capability is advertised. Native source remains uncompiled; devices are untested.

Construct with a real current `PhoneEmoteSources` for either role. Its actual
run, fixture root, candidate/process binding, private evidence root and lock
bind the lease. The actual path is `phone-emote-namespaces.json` beside the
existing source control files. General Phone cleanup refuses success while it
remains, even after a successful base cleanup ACK.

The closed outer record contains `emoteNamespacesVersion:2`, `runId`,
`fixtureUrl`, `artifactRoot`, `binding`, `payload`. The existing bounded packed
payload contains exactly one `{current,closed,pending,cleanup}` state. `current` is
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
Incomplete handshakes are retained as aborted handshakes by cleanup version 2;
they never become successful namespace advances. The owner must integrate the
cleanup input, timer, scene, image, actor and whole-run retirement checks before
enabling complete Emote capabilities.

Each request/acknowledgment/advance has a five-second monotonic bound, in addition
to the existing source lock, private-file and fixture limits. Host counterexamples
exercise independent originals, stale/foreign phases, cached fake inactivity,
saved fake native statistics, open scopes, missing files, closed-header changes,
ignored/lost commits and slow guards. They qualify test logic only.


## Cleanup and retained metadata retirement

Version 2 reads original version 1 headers without rewriting them. Its next
explicit state write upgrades the header and adds `cleanup:null`. It neither
truncates unresolved version 1 work nor changes source/input wire formats.

`begin_cleanup()` is primary-only in the lease's actual current namespace and
requires the real fixture `cleanup` activation with empty inputs. It atomically
moves the exact original partial handshake into
`cleanup:{ticket,pending,headers,inputsSha256}` and clears the active `pending`.
`headers` contains each role's actual original current control header or null;
inputsSha256 hashes the actual current normal-input header, including absence.
Frozen acknowledgments must match those actual original headers exactly. An
unacknowledged/missing actor remains explicitly unacknowledged; current never
advances as part of abort. A lost committed return is recovered by reconstruction
and the same actual cleanup ticket, not a second transition.

Every later lease guard reopens the retained frozen header's original manifests
and frames. Saved acknowledgment statistics are recomputed from those originals;
current role transcripts must retain their exact immutable frame prefixes. The
original current input digest and all earlier closed source/input headers stay
unchanged. Content-addressed manifests allow new cleanup frames while the old
prefix manifests remain intact. Deleted/replaced originals, changed inputs or
truncated/current foreign transcripts fail without dropping lease responsibility.
`assert_acquiring()` permits current role acquisitions after the abort only while
the actual same cleanup activation remains current. Normal inputs, advance and
late ordinary publication cannot reopen cleanup mode.

`retire(retain)` removes only this lease's metadata after transferring its exact
original proof. The callback must persist the complete packet before returning;
a false/failed callback retains the lease. The packet is
`{emoteNamespaceRetirementVersion:1,header,headers,roles}` with original lease and
both current role source headers plus independently recomputed native statistics.
Both current streams must exist, be ready, independently observe the same actual
cleanup ticket, and be no older than 1.5 seconds. Native override must be inactive;
the tablet and chooser controls must actually be absent. Native/source identity,
call cursors, lifecycle and input digest must agree across roles. Open observation
or GPU scopes block retirement. The callback cannot replace those measurements.

After transfer, the module reopens/verifies all originals and repeats the current
retirement calculation before discarding exactly its own control file. Slow
callbacks, changed originals, ignored deletion or a late source acquisition
prevent success. The five-second monotonic bound remains in force. This is a
metadata handoff, not proof of timer/browser/view or whole-run file cleanup.
Source and normal-input headers, originals and all other ownership remain intact.
The enclosing run owner must retain the proof and remove those resources through
its own verified retirement plan; it must also retain the run tombstone needed
to distinguish a committed lost retirement return from a new run.


## Closed-provider original ownership transfer, retirement version 2

The namespace control remains version 2 and active `retire(retain)` retains its
version-1 packet and freshness rules. Separate `retire_closed(retain,
retained=None)` handles actual provider closure. Both roles must already have
actual inactive-Rig, closed-UI originals under the exact cleanup ticket. Those
source frames stay historical: their ages are never refreshed by a new provider
query, and this operation supplies no new native, Script-work, image or complete
cleanup result. The whole feature still needs independent current native and
resource verification after the actor stops.

Its exact packet is `{emoteNamespaceRetirementVersion:2, header, sources,
inputs, roles, cleanup}`. `header` is the entire original namespace control.
`sources` is an ordered array for every segment 0 through current; each item
contains exactly the full `primary` and `actor` source headers. `inputs` is the
same-length ordered array of corresponding original primary input headers; null
is accepted only for a genuinely unissued current input owner. Earlier segments
require their actual inputs. `roles` contains the existing recomputed proof
fields for the two final cleanup originals. `cleanup` is the original inactive
phase packet, retaining the original retirement epoch/provider identity/history.

`retirement_archive` reopens all source and input original files and manifests,
recomputes each closed segment's original proof, checks the real immediate
predecessor/native/Script/widget continuity and unchanged admission policy, and
replays the exact aborted cleanup-handshake prefix. The two current native
identities/call cursors/lifecycle/source identities must agree. Current original
phase histories must exactly match the retained closed cleanup history. Input
replay validates actual SDK/Qt intents, consumed receipts, source references and
unfinished states, without converting them into acknowledged input.

The parent must durably retain this exact packet before namespace control
removal. Existing source/input controls must still match all original headers;
open capture or observation scopes block transfer. Rejected/slow retention,
foreign controls, changed files, missing role records, ignored deletion or a
substituted provider cannot report retirement. The whole operation and direct
historical replay are each limited to five seconds. A lost deletion return is
recovered only with the exact retained packet; absent metadata alone fails.
Retained retry may tolerate dependency controls already removed by the enclosing
owner, but still reopens their actual immutable original evidence files. It
returns the same historical packet without new native observations or epochs.
Source/input original files remain private handoff evidence; none are deleted.

`PhoneEmoteInputs.archive(header, source_header, ...)` provides the same bounded
historical input decoder independently, returning decoded data only. It creates
no usable input owner, adapter, UI or target transport. Existing source/header
formats, the 64 KiB control limit and 1 MiB original-file limit remain unchanged.
These host-only checks qualify test logic, not product behavior or devices.

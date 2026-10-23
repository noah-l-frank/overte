# Durable original Worlds observation ownership

`NavigationObservationOwner` owns one read-only eight-field acquisition. It
combines the existing [image index](NAVIGATION_SAMPLES.md), typed native readers,
normal UI observation and [original-state composition](NAVIGATION_PRODUCT_STATE.md).
It does not send normal user input, publish independent actor facts, admit a
scene/process replacement or retire a whole run. Worlds remains partial.

`IOSNavigationRuntime._navigation_observation_owner` now constructs this owner
through the existing `IOSScriptRuntime` candidate/session gate and actual
HTTP/AFC components. It checks the attached original provider's source revision
before creating navigation metadata. The outer observer and nested image
attempt share the same bound native clock reader, navigation reader, private
source lock and fixture attachment. Typed field readers use independent native
clock acquisitions; UI snapshots use the original native clock transport.
Changed artifact bytes, PID, session or provider context prevent further reads.
The factory cannot create a session, launch/install the app or send an input.
Role/stage separation names private ownership only; a stage number does not
establish an actual restart. Whole-run admission must prove that replacement.
This factory does not expose a complete feature operation or capability.

The private version-1 record is bound to the complete installed candidate,
run, primary/actor role, process stage, unique request, existing source lock and
the image index's private directory. It reserves the observation before reading
anything. The original phase read and outer `NativeClockAcquisition` beginning
are saved before invoking an image factory. The original native beginning and
measured host beginning retain their different clock domains.

Each newly accepted image packet, bookmark file/map, Places model, HTTP history,
dialog lifetime, lookup reply, normal UI packet and final navigation packet is
immediately saved. The image's immutable child archive is retained separately
from mutable later drainage proofs. Original PNG bytes stay under the existing
image owner's inode/hash/chunk validation; they are never regenerated from the
requested location or ticket.

The newly accepted final native packet and measured host endpoint are saved
before testing the full clock join. Thus even a rejected overlong acquisition
keeps its accepted end packet and every accepted field. Only a complete bounded
join can reach composition. Both the stored beginning and endpoint must equal
the full original join exactly. The join's digest covers all eleven originals.

Original fixture reads bracket the whole operation. Historical validation
rechecks their actual phase, navigation-provider and scene-provider packets,
hashes, immutable activation list and original provider instance. A phase
crossing prevents a complete observation; it does not authorize another input
or a new capture in the old owner. Fixture data remains input metadata.

A complete retained predecessor is mandatory once this role/stage image index
has an earlier attempt. Its file/hash and actual last image request are pinned;
an older chosen baseline cannot skip the immediate predecessor. The pure
validators require advancing native observer birth/counters/history, image
identity, navigation/scene history, all four field-source counters/clocks,
lookup/dialog history prefixes and both actual UI survey counters. No old
original receives a replacement timestamp. A changed source birth or counter
rollback prevents completion even after recreating a typed source reader.

A fully captured pending marker retains the complete sources and reports no
public state. A later owner may acquire another original image under the same
source continuity. All field and current scene checks run before accepting a
marker-pending composition; a bad field cannot hide behind a pending marker.
Uncertain source delivery or an incomplete image remains owned and cannot be
replayed by reconstructing the observation. Partial attempts are not evidence
of absence or successful cleanup. Their image index still owns explicit GPU
drainage; the whole-run finalizer must reconcile both owners.

When the image is already sealed, explicit `abandon_sources()` can retain a
failed field read in the existing version-1 `failed` phase. It validates the
actual PNG/owner, original phase and native beginning, and the exact accepted
field prefix, including independent original clocks and histories. It sends no
source query or normal input and deletes no image, owner or original. The
record differs only in its terminal phase and yields no public state. An
overlong original join or an actual phase crossing stays historical; it never
receives a replacement deadline. An unresolved image cannot use this path.

A distinct successor must name that exact failed owner as its predecessor.
It extends every accepted field counter/history and starts after all accepted
native endpoints. If the partial predecessor lacks a channel, validation also
retains the earlier predecessor's floor for that channel. Thus, for example,
a lost UI read cannot conceal a UI counter reset relative to the last complete
observation. All partial carriers and original files remain in the chain.
Historical reconstruction performs no SDK query, source retry or capture.

`recover()` only resolves a complete retained old record whose final return was
lost. It reads no SDK/native/provider source and cannot issue another capture.
For a first opened directory, `recover(directory=...)` can join its genuine
directory proof after the full raw group was retained. The ticket, provider
inputs and original HTTP/model/provider packets must match that exact group.
Another valid acquisition cannot replace them. The enclosing normal-input
owner must retain the original admission barriers; this join cannot prove that
an ignored open succeeded. A rejected join leaves the saved carrier unchanged.
Historical `archive()` reevaluates the same originals and actual retained PNG.
It keeps the original acquisition time, including when recovery occurs much
later. A fresh return additionally requires the whole operation, including
storage and validation, to remain below the existing 1.5-second deadline with
the original host clock-drift bound. An already saved late record remains
historical and cannot become fresh through reconstruction.

Host tests use real private files, actual PNG decoding and a real short-lived
loopback fixture. Native/GPU/UI/SDK responses and their clocks are modeled.
They exercise A/B state, marker settling, original file changes, source rollback,
phase crossings, lost field/final returns, early factory failure, retained late
endpoints, predecessor selection and historical no-SDK reconstruction. Native
compilation and device timing/behavior remain unverified. Runtime factories,
scene admission/restoration, ordinary input, independent publication, restart,
repeated quiet cleanup and final metadata retirement remain required.

Additional host counterexamples exercise explicit source abandonment, a lost
abandonment return, source reset through a newly constructed reader, a missing
channel hiding an earlier complete floor, changed original PNGs, original phase
crossings and overlong windows. These use real private PNGs/archives and the
existing loopback provider, with modeled native/GPU/SDK boundaries.

One historical archive round validates each predecessor's composition once.
Repeated use in that same synchronous round reuses only the checked original
result, scoped by exact path and carrier digest. Before returning, the round
rechecks every participant's actual private carrier, in-memory state and
original PNG/owner. A changed predecessor file or state cannot borrow the
earlier result. The cache is local to the current context and discarded after
every call; another archive call performs a new complete validation. This
avoids exponential duplicate predecessor work without changing source clocks,
schema, input deadlines or original bytes. Host counterexamples cover a real
four-owner chain, a PNG changed after predecessor validation and a mutated
predecessor original in memory.

The same existing synchronous round now also shares completed historical
baseline/restored PNG decoding. It first runs the entire actual typed source,
PNG and ownership decoder between independent file inventories. Every actual
read is then pinned by device/inode/mode/owner/link/size/mtime/ctime; hits and
round exit recheck those pins and the complete carrier/context. Returned values
are separate copies. Live acquisitions and any outer actual-read collector
still perform full decoding, so a caller's read-set membership cannot disappear
behind an earlier result. No live freshness, input permission, source quiet or
global inventory verdict is cached.

Profiling the existing restarted-restoration case found 450 pure process-context
snapshot validations. Snapshot/transfer/context DTOs now share complete pure
decoding within that same round, keyed by every unchanged original input,
version, scope and owner-file argument. These validators perform no I/O. A
changed byte/value obtains no old result; failed decoding is never retained.
There is no persistent cache or schema/clock/deadline change.

Four actual original-file cases cover one decode per round, independent return
copies, new-round decoding, unchanged live decoding, changed bytes in the same
inode, identical bytes in a replacement inode, round-exit changes and complete
outer read membership. Two process-round cases count actual old/new decoding
and reject changed candidate/native clock/owner/derived fields. Nine existing
process cases additionally run inside the actual round, retaining literal
versions 1/2/3 and their persistence/root/process counterexamples. The existing
restarted source/image/quiet/publication/history case remains green: measured
host duration changed from 38.321 to 34.513 seconds after image sharing, then
26.920 seconds after pure process sharing. This is one host measurement, not
physical iOS or general API timing qualification. Three original-process image
cases also pass, including literal image/state version-1 replay.

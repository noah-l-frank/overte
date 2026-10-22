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
replayed by reconstructing the observation. Partial attempts are unresolved,
not evidence of absence or successful cleanup. Their image index still owns
any explicit GPU drainage; the whole-run finalizer must reconcile both owners.

`recover()` only resolves a complete retained old record whose final return was
lost. It reads no SDK/native/provider source and cannot issue another capture.
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

# Original SNAP pending work

`feature-ios-snapshot-work` is a passive, closed, source-only query over the
existing HTTP/AFC component. It observes the real `snapshot.js` closure on its
own VM and the actual ScriptManager timer creation, dispatch, callback and
QObject destruction paths. It adds no timer, capture, UI action or permission.
The helper is loaded only when the dedicated iOS native test API is available.
Normal startup and callbacks preserve their arguments, return and exceptions.

The native caller scope supplies the actual manager/load/source identity and
code handed to evaluation. A separate Snapshot source observer records exact
UTF-16 code units and SHA-256 for the main and helper sources before evaluation.
The reviewed pin manifest is a comparison policy, not an installed-file read
presented as proof of executed code. Full admission joins both original source
identities and actual native manager state under one original native bracket.
Freshness uses original native epoch/monotonic clocks and real VM heartbeats.

Entry, return and finally events retain nested call ownership. Initial and
changed states are immutable; unchanged heartbeats advance only the latest
original. The closed reader rejects erased history, source/PID/birth changes,
nonce reuse, older clocks, a heartbeat rewritten into later history, missing
actual submitted sources and prematurely ended scripts. The state includes
capture identity/counter/mode, real delayed timer handles, pending upload count
and overlay/review visibility, without URLs, titles, filenames or credentials.

Snapshot timers use an independent native instance and the new
`snapshotTimerWorkVersion: 1` schema. The existing Avatar timer producer and
reader keep their exact default schema/filter and wire version. The shared
pure timer validator accepts explicit schema/filter keywords; packets are
validated in their original schema and never relabeled. Quiet requires no
active closure/capture/upload/overlay work and real destruction plus zero
callback depth and pending native dispatch for every observed Snapshot timer.
A singleShot QObject can die before its callback enters; weak death alone
therefore cannot qualify cleanup.

Eight no-build Python checks cover original identity/history, actual AFC and
probe preservation, strict fixture commands, pending work and timer dispatch
after destruction. The production JavaScript suite contains thirteen cases,
including the actual observed 350 ms delay and 60 s timeout before any renderer
request, real cancellation order and an actual thrown cancellation that cannot
produce a return or restored-overlay fact. The native timer paths are inspected
source only; they remain uncompiled and devices remain untested.

The [native capture lifetime component](SNAPSHOT_CAPTURE_LIFETIMES.md) now adds
actual weak request/timer/watcher originals and a pure early-cancel source join.
This is not a complete Snapshot adapter: durable normal input and independent
original files must still join that cancellation proof. Photos destination bytes
and owned deletion, an external share receiver,
normal system authorization/activity input, authenticated upload receipts and
paired final image/source quiet evidence remain required. A quiet script or
native export acknowledgment does not establish those outcomes. See
[the export component](SNAPSHOT_EXPORTS.md).

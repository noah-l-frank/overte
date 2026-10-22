# Pico normal still-PNG owner, version 1

`PicoBoundAdapter._snapshot_still_owner(target, run, phaseSource,
source_lock=parentLock)` composes the existing `PicoSnapshot`, `PicoNavigation`,
`NativeNavigationIO`, original `PicoOpenXrAdapterSession`,
`AndroidSnapshotFiles`, [native callback originals](SNAPSHOT_ORIGINALS.md) and
existing `snapshot_observation.inspect_snapshot` decoder. It provides the
normal still-PNG subset of common v16, not another output runner or a complete
Snapshot adapter. No `feature.snapshots.*` capability is advertised.

The narrow normal sequence is `prepare → open → take → quiet → close → quiet`.
Prepare binds the actual original process, candidate, native bridge and
OpenXR session and admits the empty native observation scope. Open requires
the independent fixture's actual `open` activation and uses the original VR
tablet gesture, Home pages and SNAP entry. Initial mode/format are read from
actual checked popup delegates and retained before capture. Take requires the
actual `capture` activation with `mode=still, format=png`; it selects an empty
run-owned prefix using the existing name field and real mode/format controls.
An immutable actual native request ID and complete callback are joined to
the same OS original by request ID, basename and run-salted **full canonical
path** hash. Native source v2 retains the callback's raw path hash and actual
canonical path hash separately, including a genuine OS-owned app-root alias.
The v1 reader can join only when its actual raw hash itself equals the OS
canonical hash; no alias or missing canonical provenance is inferred.
The native observer never accepts these as expected effects.

The existing file observer retains OS device/inode/full mode/UID/link count/
size/mtime/ctime with nine fractional timestamp digits before and after actual
hashing and transfer. A same-byte replacement is a different original. The
actual run-as command hashes the canonical path with the run and NUL separator;
it does not expose the absolute private path in its result. A platform `stat`
without the required timestamp precision fails this source profile. The public
`snapshot.files` DTO is unchanged. The private five-column listing uses explicit
`OVT_SNAPSHOT_FILES_V2`/`OVT_SNAPSHOT_FILES_END_V2` framing, and its retained
original has `snapshotFileOriginalVersion=2` (`android-snapshot-file-originals`
reads version 2 only). Legacy V1 three-column output and incomplete V2 output
are refused; no previous inode/path provenance is invented. The fixed Phone
reference still uses the older common V1 reader, so later shared reconciliation
must select the V2 producer and parser together. The binary transfer remains
V1 because its framing and byte semantics are unchanged.
File decoding still checks the original full
PNG bytes, encoding, checksum, dimensions, every frame, nonuniform pixels and
hash. It is byte/output evidence only. In particular, actual HMD still capture
downloads half the composite width and does not establish both stereo eyes.

`snapshot-still-owner.json` is a private process/run/fixture-bound CAS journal
with complete packed originals. Before each normal action and each final QML
command or controller envelope, the parent intent is fsynced. Original query,
request/event, QML-token/generation/sequence and OpenXR-session/envelope histories
remain bound and immutable. Every source reader uses the exact parent
`ScriptSourceLock` instance. After the last CAS and native/SDK guards, a fresh
independent exact phase read fences actual delivery. Copy/decode/guard/CAS time
counts toward the source age through native and monotonic lower bounds.

The actual Session `intent` callback performs private host CAS only; it performs
no fixture/native/SDK query or session re-entry. Its final `before_publish`
validator reads retained memory and monotonic time only, including after
transport/SDK delay. No source, file read, second intent or new input is issued
there. Every lost-response `*-issued` state remains unresolved. Reconcile reads
new original UI/native/file sources only: an actually completed lost capture
can become captured, while an ignored capture remains issued. It cannot re-open,
re-capture or re-send an uncertain command. The older public snapshot operations
cannot reset this new owner's unresolved scope.

Native quiet requires three seconds on actual native time, native UI time and
host monotonic time, gaps at most 500 ms, the same immutable PNG/OS original,
expired original native request and actual zero active requests/projection timer/
waiting flags/image buffers. Closing uses the original checked mode/format
controls and controller-close/wait route, then obtains another full native
quiet window. Initial and restored checked delegates are retained separately.
The original preference/UI journals and output file remain owned after normal
close. Adapter-wide base stop remains available, but cannot discard those
journals or qualify Snapshot retirement; it returns failure while they remain.

## Explicit partial boundary

`report()` returns `PICO_NORMAL_STILL_PNG_COMPONENT_ONLY`,
`fullSnapshotRecipe=false`, `deviceAcceptance=false`, `journalRetained=true`.
Native weak-request/timer/image-buffer quiet does **not** prove the earlier
Script request and scheduled 350-ms work, Script pending/cancel history, every
Snapshot setting (including previous review paths/stories), review/QQmlContext,
controller-neutral history, OS export/upload leases, independent receiver or
server body. There is no output deletion, observer-scope retirement or hidden
restart. `partial-closed` describes only this normal subset and its retained
originals; all required full v16 obligations still apply.

The full recipe still needs target-local normal pre-render Cancel with genuine
Script IDs/timers and immutable pending/cancel history, measured actual Save
backend/authorization, genuine OS picker/permission routes, independent saved/
receiver/upload originals, upload failure/recovery, background return and final
original settings/Script/Qt/observer/file retirement. Panorama/cubemap and stereo
require their actual original capture paths. The existing `snapshot-output-parity`
module remains the owner of its five normal output modes and decoder.

The source/host selection here uses common v16 and fixed Phone
`abb7f6b60d97daf17752aadf94e2b5df099bb7ba`. The subsequently supplied fixed Phone
`5527d540e99cc6dba4204a5e904a854e6e1cd2b4` is a separate reuse-review candidate;
this packet does not migrate the common contract or import moving Phone work.

## Verification

The `snapshot-normal-still-owner` Pico selector runs the actual private factory,
normal input classes, original Session staging callbacks, original run-as file
scripts and decoder against explicit native Qt/render/SDK/time seams. Thirteen
composition cases cover normal capture/restore/close, read-only cold recovery,
ignored ACK, lost capture response, last-CAS phase advancement, frozen native
clock plus slow CAS, delayed controller publication, native full-path mismatch,
same-byte OS/host inode replacement, forged archived quiet, closed cold command
identity/types and retained cleanup.
Seventeen existing file-source cases cover binary/framing/bounds, incomplete
reservation progress, companions, continuity and aliases. These are device-free
source/host tests, not renderer/headset/OS-export or device evidence.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 \
  android/vr/pico/tests/device/test_snapshot_still_owner.py
```

Use a private disk-backed `TMPDIR`. The generic transport API dependencies are
fixed reviewed `5bd12aa3ae`, `b28080c61e` + `1219061917`, the generic hunks from
`175fa35ac5` only, and original Session/transport `b7ffebf38b`; no Chat dispatcher
or moving context was selected.

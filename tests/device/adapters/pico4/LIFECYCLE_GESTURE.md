# Original Pico gesture consumption

`PicoLifecycleGesture` reads `feature-lifecycle-gesture.json` through the ordinary
private probe, candidate/process guard and native typed provider. The source is
owned by the actual Pico override input device, under both
`OVERTE_E2E_FEATURE_TESTS` and `OVERTE_E2E_OPENXR_INPUT_V1`. It requires the actual
private probe script/results arguments. Production builds keep their input path.

The hook runs after the original `left_thumbstick` publication into the actual
axis map. It keeps original raw/mapped values, validity, OpenXR change metadata,
frame/time cursors and append-only native gesture identities. Keepalive frames
produce no extra start. Focus/session/synchronization loss preserves the active
identity as unavailable. Only a later active, valid, actually published neutral
sample closes it. Queries never supply a gesture, count, effect or timestamp.

Each transition preserves the exact private native layer status bytes and SHA256
when available. The file must be an owned regular single-link mode0600 file in
the private input directory; descriptors/path identity and bounds are checked.
The host reuses the existing native status validator. `consumed()` requires the
original `vector-consumed` receipt, actual vector, command ID, sequence and nonce
to match the durable original input envelope. Accepted/ACK status alone cannot
qualify an attempt. Raw nonce-bearing originals stay private. Current known axes
must be fresh independently of a fresh observation query; host monotonic time
bounds final acceptance even with a frozen device clock.

Overflow, modified/truncated history, replaced plugin lifetime, foreign stream,
unsafe status file or stale current frame fail closed.
The original Pico `getVector2f()` failure returns `isActive=false`, so it already
invalidates publication; the dedicated success flag additionally preserves the
explicit `vector-query-failed` cause without normalizing failure into neutral.
The native host fixture executes that original function body, including its
actual unsuccessful-result branch. Status admission compares descriptor and
pathname device/inode, full mode, UID/GID, link count, size and original
mtime/ctime nanoseconds before/after reading. The actual layer writer uses a
private temporary plus rename; in-place changes are rejected too. Unavailability is never
neutral. Native status retains its original last applied vector through neutral
windows; neutral comes from the client's published axes, not a rewritten receipt.

The Qt5 host compiler executes the original Pico override axis block with real
`AxisValue.cpp`, this source and explicit OpenXR action/status boundaries. Python
checks execute the real adapter factory and original probe branch. These are
source/host checks, not an OpenXR session, complete plugin/TSI build or device run.

This packet supplies original consumption and neutral evidence. It does not yet
qualify the whole Lifecycle journey: durable operation ownership, independent
avatar displacement/peer evidence, typing/pending commit/context replacement,
background return and final resource release must be joined separately. The
existing normal X owner still reports a surviving original QQmlContext as
retained; page destruction does not imply context retirement.

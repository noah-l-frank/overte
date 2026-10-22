# Pico Snapshot native originals, version 1

This is a private source component for the existing shared Snapshot journey.
It does not advertise `feature.snapshots.*`, perform a capture, qualify an image,
or complete the eighteen-input common v16 recipe.

`PicoBoundAdapter._snapshot_native_originals(target, source_lock=parentLock)`
uses the existing ScriptJourney `script-sources.lock` instance, verified
candidate/process, private Probe command channel, and the actual native
`Snapshot` dependency. The closed command has `schemaVersion`, `commandId`,
`runId`, `action=feature-snapshot-capture-originals` and `operation=arm|read`.
`arm` admits one empty native scope; it cannot reset an existing scope. The
read-only result is `feature-snapshot-capture-originals.json` using the existing
private test-result writer. Dedicated `OVERTE_E2E_FEATURE_TESTS`, actual
`--testScript`, private started test results, Pico/HMD and original owner-thread
checks all remain required. A non-Pico getter returns unavailable.

The original `Snapshot::beginCapture` inserts an accepted ticketed request into
its actual map before observation. The source retains a `std::weak_ptr` to that
same control block, an immutable native birth, original request ID and actual
registration time. It never prolongs the request lifetime. The existing
`captureStatus` and `cancelCapture` paths append their actual callbacks immediately
before the original signal emission. Callback paths and basenames are hashed
with the run and a NUL separator, never published as private paths. No requested
phase, filename, click, acknowledgement or expected effect enters this history.

Each frame also reads the original active map size, six projection QImages'
allocated bytes, taking/waiting flags and projection timer on their actual GUI
owner thread. Bounds are closed: 32 original requests, 16 events per request,
4096 unique commands, and 64 KiB raw result. Overflow or an unmatched callback
is unavailable; there is no eviction or history reset. The TSI uses its own
bounded weak Qt queue; a blocked queue times out without accepting or replaying
late work, and subsequent queries wait for actual pending-functor retirement.

The Python reader retains exact native raw bytes and their hash. Cold cursors
validate both original frames, immutable request/event prefixes, process/run/
instance and increasing query cursors. A dead original control block cannot
revive. Final copy/accept/guard work is covered by both the actual source clock
and monotonic lower age bound, including when either clock is frozen. An
unanswered query is never resent.

## Actual capture boundary

The earlier Script request/timer is a different scope. `snapshot.js` waits 350 ms
before hiding the tablet and at least another render delay before invoking the
native capture. Native accepted-request registration therefore cannot prove
the required earlier `pending,cancelled` history or fast normal Cancel. That
requires original Script ID/work and normal visible-control acquisition.

`Application::takeSnapshot` submits the real SnapshotOperator, and
`OpenGLDisplayPlugin::present` obtains `getScreenshot`. That getter halves the
composite width when `isHmd()` is true, then downloads that region. A normal
still PNG consequently does not prove both stereo eyes. Panorama/cubemap have
their own original secondary-camera path and need independent evidence for
orientation and scene fidelity. The existing `snapshot-output-parity` decoder
continues to own encoding, dimensions and complete image-byte checks.

Native request expiry plus empty native resources can prove this narrow lease
scope only. It does not retire Script work, review/Qt contexts, private capture
files, OS-saved originals, receiver deliveries or authenticated upload bodies.
No restart or force-stop acknowledgement substitutes for those closures.

## Device-free verification

`snapshot-native-originals` registers five reader counterexamples, the actual
private Pico factory, original Probe dispatch under Node, and a Qt compiler/run
check. The native check compiles the complete original Snapshot begin/status/
cancel/source and TSI getter bodies, original production request type and
bounded Qt queue for Pico and non-Pico, with and without `--testScript`.
Renderer, platform, secondary camera and dependency registry are explicit host
seams. It tests real queued callback lifetime/cancellation, weak retirement,
same-text-ID replacement, duplicate commands, absent dependencies, malformed
queries, blocked queue timeout and rejected late work. It is no headset,
renderer, export, or physical-device evidence.

```bash
PYTHONDONTWRITEBYTECODE=1 OVERTE_NATIVE_QT_MAJOR=5 \
  OVERTE_QT5_HOST_ROOT=/home/user/.local/overte-qt5/root \
  python3 android/vr/pico/tests/device/test_snapshot_originals.py
```

Use a caller-owned private disk-backed `TMPDIR` for compiler temporary files.
The fixed Phone reference `abb7f6b60d97daf17752aadf94e2b5df099bb7ba`
provides the older normal output-parity adapter, not a complete Snapshot v16
implementation; no moving Phone source was used.

# Original normal Pico X/Back owner v1

`PicoLifecycleBack` implements the first normal Create Back route as a partial
Lifecycle/input primitive. It does not advertise `feature.lifecycle-input.*`.
The real adapter factory is `_lifecycle_back(target, run)`. It reuses the actual
verified candidate, installation, process identity, original shared OpenXR
session and private normal-feature binding. No locator, requested effect or
expected editor is sent to the passive Lifecycle source.

`back()` first observes an actual visible Create field, page and valid canonical
QML context on the shown 3D tablet. It writes a private candidate/process/run
journal, then persists the exact original OpenXR nonce, sequence and envelope
under the session lock before any transport write. Only this one bounded
`controller.button` input is sent: left/primary, 120 ms. The existing original
`pico-tablet-x-back` callback receives that X action and returns the shown page
to Home. This primitive never calls Home, a QML handler or an effect setter.
The new optional session `intent` callback is a pure host CAS/fsync operation;
it must never reenter the session, a device guard or ADB while that lock is held.
Existing callers retain their existing behavior.

The input ACK is ignored for effect qualification. Separate original Qt/VR
observations must show the tablet still shown on Home, no current editor, the
original field and page actually destroyed, no focused retained editor, all
real VR keyboard layers hidden and every real key released. Both native source
timestamps and host monotonic time must span three seconds. The independently
read exact nonce/sequence stream must be neutral before and after that window;
its original native status, including unchanged `updatedEpochMs`, is retained.
A historical neutral timestamp is never rewritten into a new sample time.
Original sample age remains bounded through the final status read, host journal
compression and identity guard; a two-second final delay cannot pass merely
because the device clock froze.
This proves neutralization of this owned stream, not all physical/world input.

A surviving original context is explicitly `retained`, even when its field/page
have died. The report preserves all five actual object-liveness flags and sets
`editorRetired` only if field, page and context are all dead. Qt5 can retain an
invalid QQmlContext wrapper after page destruction; this route does not delete
that wrapper or reinterpret it as destroyed. Hidden/detached old pages cannot
qualify this route checkpoint. Missing/foreign/malformed native data, ghost keys,
held keys, failed neutrality and stale source clocks fail with ownership intact.

`reconcile()` only reads the original committed stream and fresh original
sources. A lost ACK can reconcile without another input. An uncertain grant
commit whose host sequence never advanced, a failed durable intent, another
process/run/candidate/session or a newer unrelated input cursor remains
unresolved. Calling `back()` again cannot resend even after a failed reply.
Read-only reconciliation also restores the original append-only Qt/keyboard
history across host process reconstruction.

The private journal contract is `pico-lifecycle-back-owner:1`. Its outer fields
are exactly `lifecycleBackOwnerVersion,runId,binding,payload`; the compressed
bounded payload contains one exact state with `phase,originalId,envelope,frames,
neutral,quiet`. Frames retain the original JSON bytes plus their SHA-256, with
native/keyboard instances, advancing cursors and irreversible per-object
retirement. The existing private history codec bounds decompression to 16 MiB
and encoded payload to 48 KiB; this primitive also bounds history to 128 original
frames and each attempt to ten seconds/41 source captures. Serialization uses a
stable private lock inode; no uncertain journal is retired or truncated.

Even a measured `released` report retains the journal for the missing final
Lifecycle feature join. Base Pico cleanup checks this ownership after ordinary
teardown and fails while that journal exists. Stopping the app cannot make the
unresolved feature successful. This packet does not complete context-generation
aliases, Create Unicode entry, actual tracking/focus/world held-input inventory,
PendingFieldCommitOwner composition, independent avatar-displacement/stale
rejection publisher, background/resume or full sixteen-step/role cleanup.

Focused host checks, with a private disk-backed `TMPDIR` and
`PYTHONDONTWRITEBYTECODE=1`:

```bash
python3 tests/device/self_tests/test_pico_lifecycle_back.py -v
python3 tests/device/self_tests/test_pico_lifecycle_x_mapping.py -v
python3 -m unittest tests.device.self_tests.test_pico_openxr_adapter_session -v
python3 android/vr/pico/tests/device/test_lifecycle_input.py -v
python3 tests/device/validate_contract_versions.py
python3 tests/check-documentation.py --all
git diff --check
```

The owner/session tests use explicit synthetic native/OpenXR boundaries. The
Node test executes the unchanged original product mapping with explicit
Controller/Tablet boundaries. The wrapper check executes the actual Pico
candidate guard and transport binding against synthetic native replies. These
checks establish no physical Pico/OpenXR execution, VR input, independent peer
or complete Lifecycle result. Native editor lifetime/focus has a separate real
Qt5/NativeCreate host check in [the source packet](LIFECYCLE_SOURCE.md).

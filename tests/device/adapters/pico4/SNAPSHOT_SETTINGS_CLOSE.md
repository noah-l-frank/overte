# Raw thirteen-key observation after normal Snapshot Close

`PicoSnapshotCloseOwner.observe_settings()` composes the existing normal Close
owner with the passive [pre-input lease](SNAPSHOT_SETTINGS_BASELINE.md). It
requires the actual new-run Cancel v3 parent, its original baseline SHA, the
same exact source-lock object and its original first-input envelope. Old runs
without this original cannot create it after capture, upload or Close.

The method runs only after the existing normal Mode/Format controls have
restored their original checked selections and the original controller Close
has produced a closed generation and independently observed Neutral. It first
records another actual closed frame/status. A private `read-issued` CAS pins
that frame, the original phase/controller/generation, baseline identity and
the exact next baseline observation index. The existing final Close phase
fence runs after that CAS and before the passive native getter. The immutable
raw source is retained in the existing baseline original container; a second
actual closed/neutral frame bookends it. Native capture timestamps and host
anchors establish ordering. Neither input acknowledgement supplies a bookend.

`snapshot-settings-close.json` is a private version-1 checkpoint. Its exact
references are checked on every cold reopen, including original frame hashes,
raw-source continuity and the original baseline SHA. A crash after the child
observation CAS adopts exactly that already committed answer, without another
source query or ordinary input. A fresh read is allowed only when that child
index has no answer; this is a passive query, never a replayed product input.
Multiple later answers cannot fill a missing checkpoint. An expired captured
answer stays retained and cannot be silently replaced or accepted as fresh.

Report construction and all checkpoint CAS work precede the final Close
phase/guard fence, followed by a final native-clock read and the original
source's monotonic lower bound. A device-clock freeze cannot conceal a slow
CAS. A native jump in the final guard rejects the result. All originals and
the unresolved checkpoint remain. Its filename independently blocks ordinary
base cleanup, including when no other parent journal survives.

The result exposes exact typed-state equality, changed entry projections and
changed cache projection. `settingsRestored`, `continuousQuiet`, whole recipe
and device acceptance stay false. The checkpoint neither reuses an earlier
quiet result nor runs a shortened quiet window: a subsequent `close.quiet()`
must acquire its ordinary complete three-second window. Reopening a completed
checkpoint only validates the retained result and its original age; it does
not refresh clocks or issue additional input.

## Executing product restoration boundary

The actual normal controls restore selected mode/format, not arbitrary raw
state. `scripts/system/snapshot/NativeSnapshotReview.qml:179` sends the normal
mode action, and line 200 calls `Snapshot.setSnapshotFormat(currentText)`.
The normal getter in its line-198 component initialization also initializes
the format Handle through `Snapshot::getSnapshotFormat()` in
`interface/src/ui/Snapshot.cpp`; returning the displayed selection cannot
undo that original initialization flag.

The executing script makes further changes independently of those controls:
`scripts/system/snapshot.js:119` writes nine previous-image entries to empty
strings/false on the setup path. Its `takeSnapshot()` at line 514 writes the
mode at line 521, resets those nine entries at lines 527–535, and writes the
actual capture href/domain at lines 545 and 547. Capture completion writes
the actual new image path, and successful upload writes actual story/URL
entries. These are ordinary product operations, not test-set expected values.
No existing mode/format/Close control restores the former presence and typed
contents of these arbitrary entries or clears the initialized native cache.
No setter, product control, settings-file edit, Handle reset or restart is
introduced to hide that boundary.

The shared recipe still executes mandatory Close at
`tests/device/feature_journeys/scenarios.py:284`, then the real engine cleanup
path in `tests/device/feature_journeys/engine.py:500` activates cleanup, calls
the bound cleanup operation twice, and requires the original baseline for
three seconds at line 513. The declared state baseline at scenario line 265
does not itself contain these thirteen raw entries or native cache flags;
passing that visible-state equality cannot stand in for raw restoration.
This checkpoint does not replace that requirement, weaken its original
equality or retire process-wide export resources. A full
new-run Close/cleanup parent must carry these raw originals forward and refuse
complete restoration when the raw state differs. Historical runs lacking a
pre-input lease remain explicitly incomplete.

## Focused host proof and seams

`snapshot-settings-close` exercises the actual new-run passive reader/factory,
private native raw-source receipts, normal first Open, actual controller
Session and the original baseline/checkpoint CAS. It checks changed paths and
cache without writing either back, persistent cold reopening, interruption
after the child's original CAS with zero further query/input, altered original
frame rejection, native-clock advancement during the last guard, a frozen
native clock plus slow final CAS, expiry and refusal without an original lease.
Native/Qt serialization, GUI/SDK and time remain the existing explicit test
producers. The closed frame/neutral bookends in these focused tests are an
explicit source seam; the separately owned `snapshot-close-owner` tests prove
the actual Mode/Format/Close normal transport. These cases do not constitute a
new warm end-to-end chain from the fresh thirteen-key lease through Save,
Upload, return PNG and Close, nor a device or independent-actor result.

The final disjoint selection passed 2/96 local catalog groups in 20.11 s:
`snapshot-settings-close` 20.050 s (6 cases), coverage 0.057 s. The separate
actual orphan-cleanup factory case passed in 0.057 s. Repository policy,
policy consistency, documentation and source-layout checks passed in 2.41 s.
The original new-test probe had a wrong unwrapped-OSError expectation and
advanced its test clock in the early fence instead of the intended final
guard; those harness errors were corrected before these results. The real
source lock's rejection and freshness limits were preserved.

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=<owned-private-tmp> python3 \
  android/vr/pico/tests/pico4-test-suite.py \
  --test snapshot-settings-close --test coverage-matrix \
  --junit <owned-private-report>
```

No new native compiler, device, installed client, system chooser or remote
service was used for this packet. Native raw-settings serialization/source
ownership remains covered by the separate `snapshot-settings-originals`
compiler suite; it is not reclassified as a complete product run here.

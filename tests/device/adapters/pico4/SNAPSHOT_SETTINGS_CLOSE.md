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

Final admission also follows the actual outer source-lock exit. It requires
that no enclosing acquisition remains, freshly verifies this checkpoint, the
original baseline header and its immutable raw-source children, and checks the
same closed-frame references and parent state after the final candidate guard.
The final native-clock read is followed by the host-clock read, so time spent
in that read is charged to the original raw-settings query and original Close
phase fence. Neither lock release, physical verification nor cold reopening
renews an anchor. A delayed exit or changed original refuses with the observed
checkpoint and raw answer retained; recovery can only validate that same
answer, without another source query or normal input.

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

## Outer-exit correction (2026-11-02)

Two new counters first failed against the previous owner: an actual outer lock
exit delayed by two host seconds while the native clock stayed frozen, and
replacement of the checkpoint after actual release. Both previously returned
success. The corrected existing owner rejected both, including an expired cold
reopen with no repeated source query or input. Two additional counters cover
baseline replacement during the post-exit candidate guard and a delayed final
native-clock read with a frozen returned epoch. The first ten-case run passed
in 11.511 seconds with all 148 loaded local source files unchanged.

Review then found a further concrete post-guard boundary: changing an original
closed bookend after exit could still return the earlier report. That separate
counter failed in 1.194 seconds; final admission now checks the original parent
state hash and validates the same bookend references after the guard. The final
eleven-case owning run passed in 12.871 seconds; all 148 loaded local source
files remained unchanged. Its exact hashes and full output are retained in
`/home/user/.local/state/pico-snapshot-close-exit-final-20261102-iwypcent`.
The original two-case RED, intermediate ten-case
GREEN and separate bookend RED remain preserved; no failed run is discarded.

These are the existing explicit closed-native/Qt/SDK/time producer seams with
actual private files, factories, source lock, raw-source history, normal first
Open and original controller Session. This correction adds no wire version or
selector, setter, chooser driver, hardware observation, permission, upload,
callback retirement or physical Actor proof. The separate whole warm chain's
120.118-second failure remains unresolved and was not retried. Raw-state
restoration and complete Snapshot qualification remain false.


## Newer frozen Phone lease review (2026-11-03)

The read-only comparison also inspected frozen Phone commit
`5e8ff8aa19571f5718b982dc47a165b8f22e0dc0`, including
`PhoneSnapshotSettingsLease.h`, `PhoneSnapshotSettingsKeys.h`, and the original
Snapshot/Setting Manager implementations. Its native lease2 is useful design
material: native-owned originals, exact current-state digest admission, a stable
restore ID, partial-progress recovery and a closed-owner retirement condition.
Host commands cannot provide replacement keys or desired values.

Its baseline is different. The actual Snapshot read lambda calls
`_snapshotFormat.isSet()` and `.get()` before capturing the raw entries. Both
ordinary Handle paths may initialize the Handle. The lease captures only
`format {set,value}` after that initialization; it does not capture Pico's
passive `formatCache {initialized,set,value,defaultValue}`. Its set/remove
restoration therefore cannot establish equality with an originally uninitialized
Pico cache. `Setting::Interface::deinit()` saves and removes the registration,
but does not reset the original initialized flag or weak Manager association.
Calling it is not an inverse of initialization.

Reusing the protocol requires a real Pico closure/ownership proof, its retained
capture/upload/callback obligations, original GUI-thread authority, and exact
raw-map/cache compare-and-swap restoration from the already captured passive
original. Phone's UI/closure and initialized baseline cannot replace these. No
lease is acquired retrospectively, no setter/reset is selected here, and the
original thirteen-key/cache equality remains required. The source comparison
adds no native compilation, changed result schema or complete Snapshot claim.


## Animated duration is outside the existing thirteen-key scope

A further current-source audit identifies another original state that complete
Snapshot retirement must preserve. `SnapshotAnimated::captureFrames()` posts its
frame callback to the original application thread and calls the actual static
`Setting::Handle<float> snapshotAnimatedDuration.get()`. The Handle can therefore
initialize during an ordinary GIF capture. `Interface::init()` registers that
actual Handle and `Manager::loadSetting()` indexes `_settings[key]`; an absent
key can acquire an invalid QVariant entry, and a present convertible value can
be loaded through the native float Handle. Its cached value, initialized/set
flags and original registration are separate from `_snapshotFormat`.

Current passive SettingsOriginals1 deliberately captures its original fixed13
keys and only the format Handle. It cannot prove original duration-key/cache
equality. Unchanged13-key bytes and `formatCache` therefore remain scoped
evidence; they must never qualify complete Snapshot settings restoration after
GIF. This observation does not invalidate their existing explicit partial
results or provide a new restore endpoint.

The next complete pre-input scope must explicitly version and retain the
actual duration raw presence/type/value and float-cache/default/initialization
state, together with the original Manager/Handle registration. It must acquire
those originals before its first normal input and any `.get()` initialization.
Return requires the actual GUI-thread/capture/callback/upload closure, an exact
current-state CAS, original writer/persistence responsibility and independent
rereads. Neither ordinary `deinit()` nor retrospective lease acquisition is an
inverse of the original uninitialized state.

This extra duration key is also distinct from the newer Phone lease2's added
`previousAnimatedSnapUrl`. Matching key counts cannot establish matching scope.
The current Pico script has no write of that Phone URL key. Other declared
Snapshot Handles are not added merely because they exist: the duration getter
is an actual reachable normal GIF path. This is read-only source evidence; no
Handle, product behavior, protocol, source version or Native binary changed.

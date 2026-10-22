# Original Snapshot normal input reception and return

The gated native normal-input observer now has a separate Snapshot instance,
history, native clock and sequence. Its default Avatar factory and version-1
Avatar DTO remain unchanged. The new closed action
`feature-ios-snapshot-inputs` writes `feature-ios-snapshot-inputs.json` with
`iosNormalInputsVersion: 1` and actual `profile: snapshot`; it is not an Avatar
packet translated by the host.

`NormalUiInput::request` identifies the actual current capture/export control
from the native token table and the selected trusted Snapshot QML root. It
records the actual outer request, inner command UUID, control ID and root birth
before calling the existing `edit` exactly once. It records the actual returned
receipt afterward. No click, slot, capture, cancellation or export is introduced
by the observer. All hooks are gated by E2E and iOS.

Only the five capture controls and the actual Save/Share/Upload/cancel rows are
admitted. Only activation or controlled-name/empty-name replacement is retained.
Foreign text, login/private controls and unsupported commands are excluded
before entering the source history. The existing input handler still decides
eligibility and delivery. Radio-popup option controls, panel entry/Home/Close
and UIKit system sheets are not covered by this source.

The native history retains actual received/returned events up to its closed
512-event and 512 KiB event bounds. Overflow permanently fails completeness.
The separate passive getter, fixture allowlist, one-read-per-nonce probe branch
and AFC factory preserve those originals. Compact serialization stays within
the unchanged 1 MiB reader limit; no generic decoder limit changes.

`snapshot_inputs.delivered` joins a previously retained exact native command,
control and root to a single actual positive native return. A lost caller
return can therefore be resolved by a new passive read, without another input.
Missing/rejected/partial reception, changed tokens/UUIDs/roots, stale or rewritten
histories and a different profile cannot resolve it. This is a historical input
delivery proof only: `productOutcomeRequired` stays true. It supplies no capture
history, pending cancellation, bytes, export success, UI closure or quiet result.
The outer owner must durably retain the exact command before its initial send.

Nine no-build host tests exercise the real Python normal-input HTTP/AFC paths,
actual JavaScript probe and fixture/factory dispatch over explicit modeled Qt
and native event producers. A lost return occurs after the actual modeled
native receipt and is resolved with no second edit POST. These tests do not
execute the new C++ source, compile a client or qualify a device. Native code
remains uncompiled; whole Snapshot input/file/image ownership, all system-sheet
recipes, independent witness, restoration and paired retirement remain open.

## Durable ordinary input owner

`SnapshotInputOwner` owns the exact command and complete original control
reference in a private, run/role/candidate/process-bound journal. It pins one
actual Snapshot root. `reserve` persists the command UUID; `send` checks a fresh
unchanged original token/root, then persists `issued` before the existing
ordinary native delivery. A retained issued or delivered event cannot send
again, including after reconstruction. The positive original AFC return is
retained; it proves delivery only.

`recover` resolves a lost return from the actual Snapshot reception history.
Before accepting it, the owner writes that complete source to an immutable,
inode/hash-bound private `OriginalFrameStore` file under its own namespace.
Planned/opened/saved storage states are durable. A lost completed file return
is adopted by reading that original locally; no source query, edit or file
rewrite occurs. An incomplete opened file remains retained, blocks replay and
cannot be treated as a positive receipt. Its original inode/bytes are preserved.
The source validator enforces the native 512 KiB event budget independently of
the larger transport limit, so a complete typed recovery packet plus its storage
envelope fits the existing 1 MiB original-frame bound.

Eight additional no-build owner tests cover durable pre-send UUID/intent,
lost native and saved-file returns, interrupted empty files, wrong/rejected
originals, replaced roots, changed bytes/inodes and a purely historical reader
that cannot construct or query a native SDK. The historical proof reopens real
originals without retiming their clocks. No discard/retirement or product-effect
API is supplied by this input owner. Whole capture/cancellation facts and file,
image, companion/system-sheet, actor and finalization integration remain open.

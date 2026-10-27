# Tablet original-history continuation: review draft

This is a contract proposal with an isolated blocked-only fencing codec and a
defensive reader hook. `tablet_web_rotation_fence` can encode/decode only a
Source3 `rotating` fence; it cannot select a segment, produce Ready3 or
authorize native acquisition. The SourceOwner hook blocks this state directly
after the existing head read and before original/child construction. Active
Source writer2 and its literal1/2 readers remain unchanged; no registry version
is promoted. The current runtime still has its literal limits and cannot
qualify the complete common Tablet journey.

## Concrete existing limit

The current 26-step scenario contains 12 phases for which
`IOSTabletWebFeature.active_original` captures original screen evidence:
steps 1, 5, 6, 7, 9, 10, 11, 13, 14, 15, 19 and 24. The common wait requires
three progressing samples. Consequently at least 36 screen samples per role
are needed; `TabletWebSamples.capture` and `decode` allow 32. The third stable
sample in inline Open, step 19, already needs sample 33.

Primary additionally needs at least 139 aggregate frames before baseline and
cleanup: 25 ordinary action-before captures (background/resume uses its
separate owner), 78 public observations and 36 image-after captures. Aggregate
and component journals currently allow 128 records. The retained incomplete
prefix corroborates the counting: Primary 24 / Actor 19 aggregates, four screen
samples each and Primary 31 DOM captures after the normal B navigation.

More wall time or a faster decoder cannot remove these capacity failures.

## Existing storage primitive

`adapters.original_frame_store.OriginalFrameStore` already provides immutable
`append`, `manifest` and `restore`. Its block size is 128 and global frame
bound 1024; Avatar and Emote already use these methods. Manifest references
bind block/count/hash/bytes. Every frame reference additionally binds its
actual device/inode and original byte hash. Earlier manifest snapshots are
retained and, under original membership collection, read as owned prefixes.

Tablet currently writes individual original files but keeps their references
in flat active heads. Its raw packet segmentation divides bytes, not logical
history; it does not solve the flat 128-record or 32-screen limits.

## Proposed closed-header reference

Use the existing original-frame/manifests primitive rather than a new file
store or a changed limit. A proposed immutable closed-header body has exactly:

```
tabletWebClosedHeaderVersion: 1
binding: unchanged physical feature context
runId, role, fixtureUrl, processId: unchanged scope
channel: one reviewed Tablet aggregate/component/screen profile
ordinal: storage-header order only
previous: null or exact immutable prior closed-header reference
header: exact original header bytes plus its original file identity
firstIndex, lastIndex: original global record indexes
manifests: existing OriginalFrameStore manifest references
lastRecord: exact original final record reference
```

The profile must close the permitted header basename, record namespace and
schema. A caller cannot supply arbitrary paths, a new target, a changed
candidate or an unrelated prior header. The precise basename/codec choice
requires review before implementation. Native packets, references, raw query
IDs and original timestamps are preserved byte-for-byte; the descriptor adds
storage ownership only.

The current flat active-header limits remain 128 aggregate/component records
and 32 screen records. A new explicitly versioned continuation head references
closed predecessors plus its own bounded active portion. The existing global
original-frame bound 1024 remains in force; there is no unbounded stream.

Screen blocks need a 32-record active head, not a change to the shared
128-entry immutable manifest primitive. Global original indexes remain
continuous even when a live head starts at 33. Existing original PNG names,
nonces, raw fragments and their native capture receipts remain owned. No app
generation or storage ordinal replaces a native source counter.

## Original continuity and replay

- New head, header and manifest readers use explicit new codecs. Old Source 1/2
  and Screen 1 remain literal readers. No old WAL is silently normalized or
  reset. A frozen predecessor is never rewritten as an empty successful head.
- Every transition keeps the exact binding, run, role, fixture, process and
  original candidate generation. A storage ordinal cannot change
  `binding.generation`, a native instance, native sequence, phase instance or
  a captured clock.
- Original global indexes are gapless and unique across closed headers and
  the active head. Header order and range are bookkeeping, not source proof.
- Replay opens every predecessor and its exact original references, then runs
  the existing literal native/phase/admission continuation validators across
  the boundary. The native floor comes from the actual last validated native
  packet, never an integer invented from a segment number.
- Child query/raw floors, reconciliation entries, unsafe originals and app
  admission references remain part of the complete prefix. A new live head
  cannot hide any earlier failed or unresolved responsibility.
- A header can close only after existing validation proves its current
  ownership has no unresolved pending query, partial original, manifest write
  or child responsibility. Existing candidate, lock, inode/hash and current
  time guards remain at their original boundaries.

## Once-only persistence boundary

The first transition fences the existing canonical header path with an
explicit new writer tag and `phase: rotating`. Aggregate/component old
writers 1/2 must encounter Source 3 and refuse it. Screen's literal writer 1 also
requires a separate explicitly unsupported-by-old-readers new tag. No separate
optional side journal may leave the old canonical head usable.

The rotating fence contains the exact previously read header bytes, their
SHA256 and observed signature `(dev, ino, mode, uid, gid, nlink, bytes, mtimeNs,
ctimeNs)`, its literal codec version, its original scope/range/last-record
references and one copy/manifest intent. Encoding may compress the exact old
bytes but must not reserialize or normalize them. The fence must fit the
existing 65,536-byte `PrivateFeatureState` bound; failure to encode/admit it
blocks before CAS, without weakening that bound.

1. Under the actual source lock, read/validate the existing literal head and
   child originals, capture its raw bytes/signature and verify unchanged
   binding/role/run/candidate/native floors. Capture no new product data.
2. Use `PrivateFeatureState.write(fence, oldParsedHeader)` at the same path.
   This primitive is structural CAS under the source lock followed by atomic
   `os.replace`, not a kernel inode-CAS. Signature checks must therefore remain
   explicit; a hash alone is not authority. A lost CAS return must discover
   this exact new fence read-only, never restore a lower writer 2 head.
3. Only after the fence exists may the immutable segment/header copy and
   existing manifest be born. The source head was mutable WAL: its observed
   old identity is documented, not claimed as the identity of the new copy.
   The copy has its own actual FrameStore device/inode/hash. Native original
   frames and PNG files are never renamed, deleted or recreated.
4. Unknown/partial copy or manifest return remains `rotating` with one owned
   intent. Exact original-file inspection may prove a complete saved copy;
   it may not invent a missing writer ACK, native result or native timestamp.
   Recovery cannot acquire a new native packet, issue another screenshot or
   retry the product input. An incomplete or mismatched copy remains blocked.
5. Validate the copied old header with its literal reader and recompute its
   native/phase/admission floors from all exact original references before a
   new active portion is admitted. Only explicit completion advances the
   continuation head. Invalid/uncertain new metadata never falls back to a
   lower flat-header floor; actual Source/SDK ownership stays held.

The new defensive entry rejects/retains `rotating` immediately after the head
read, before original/child construction or native-source acquisition. The
frozen old literal implementation also rejects an unknown source tag in
`_history`, after purely reading existing children and before `capture`/input.
Retained bootstrap admission/SDK continuity reads remain unchanged and do not
establish any new source observation. Version routing does not catch an
unknown-tag failure and retry Reader 2. Ready/segment selection is absent.

## Required independent counterexamples

Before runtime integration, focused cases must demonstrate:

- Boundary 128→129 (sources) and 32→33 (screens) retains original file identities
  and monotonically follows actual native packets, without changing any cap.
- Foreign role/run/fixture/PID/candidate, a copied binding generation, an
  arbitrary header path and a foreign predecessor are rejected.
- Missing, duplicate, reordered or gapped references and a rehashed native
  sequence regression fail even if storage ordinals themselves advance.
- Same-byte inode replacement, same-inode rewrite, symlink/hardlink and
  mid-read child/header mutation invalidate the complete prefix.
- Pending native input/query, unsafe/rejected raw, partial opened frame,
  unresolved manifest and failed reconciliation cannot close a header.
- Lost save/CAS return preserves one intent; recovery is read-only, does not
  acquire a new native packet or image, and never falls back to a lower floor.
- Old literal Source 1/2 and Screen 1 bytes remain readable without rewritten
  clocks, IDs, counters or compatibility normalization.
- Final inventory, double cleanup and both worker/SDK endings still account
  for every sealed header, old PNG and immutable frame. Closing storage is
  never evidence that the UI, process or actual resource has retired.

The first review should approve one narrow storage/reader boundary and its
counterexamples. Full runtime routing and another whole-journey attempt remain
separate qualification work; Feature 7 and the source-complete 5/14 count stay
unchanged.

## Current focused primitive implementation

The codec preserves exact old header bytes in a bounded compressed capsule,
including noncanonical literal1 whitespace and the observed old mutable file
signature. It rejects incomplete parent/app ownership, foreign scope, invalid
identity and duplicate JSON keys. Only monotonic planned/opened/saved copy
intent metadata is supported; even a completely readable copy remains fenced
and does not manufacture an ACK or Ready state.

Eleven initial real-file cases pass in 0.172s. They exercise structural
PrivateFeatureState CAS, a lost successful CAS return, stale-CAS refusal,
copy-before-fence denial, the copy's own actual inode, lost opened/complete
copy returns, literal old bytes, foreign scope and codec limits. Thirteen final
cases, including two actual constructor entries, pass in 0.199s. The constructor
cases block every original/child/capture factory and prove both valid
`rotating` and invalid `ready` refusal. Existing SourceOwner12, Sources4 and
Source7 cases pass separately in the 36-case selection; only the new constructor
fixture URL needed correction before its final13-case rerun. These are
metadata/storage tests; they qualify no native floor, observation, segment
completion or full journey.

The five approved no-build project suites pass in 6.76s for this four-file
fence packet. Source writer2 and the contract registry stay unchanged.

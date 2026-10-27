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

## Child-bound rotation profile and read-only predecessor

The next isolated profile keeps Source3/`rotating` and adds its own explicit
`tabletWebChildRotationVersion: 1` with closed profile
`tabletweb-native-child-prefix`. A new profile can be prepared only while the
actual canonical parent is still literal Source1/2. Old unbound Source3 fences
remain literal blocked metadata and cannot be enriched after the fact.

Before CAS, the preparer runs the existing full parent/child histories and
captures all nine canonical child headers. Each descriptor contains exactly
component, derived header basename, actual byte hash and full file signature,
literal packet-header version, count, exact final original reference and
unchanged raw-fragment cursor. These are independent child tails, not inferred
from the aggregate ordinal. Unresolved pending/query/raw/app ownership blocks
preparation. A complete original inventory brackets the capture.

The copied body has its own `tabletWebChildClosedHeaderBodyVersion: 1`, same
profile/scope, literal parent capsule and all child descriptors. Only an actual
complete readable original copy can enter read-only restore. The canonical
head stays `rotating`. Restore verifies every current child header byte/inode
signature, reads the exact immutable copy and loads its old parent through the
existing literal SourceOwner history with `historical=True`. Every child
history is then replayed through its real last record, preserving its native
query IDs, packet sequences, clocks and raw/record floors. Capture/save remain
unavailable; neither a complete copy nor a hash grants Ready3.

The independent tail counterexample models an additional input-channel DOM
query after the last complete aggregate. Its new original can report
`unavailable` while the retained aggregate still contains the earlier ready
DOM. Restore must retain the actual newer disposition and sequence. Such a
disposition proves neither current document availability nor disappearance,
UI/resource retirement or permission to ignore a failed input. It is original
history only. The earlier aggregate and generated JS bytes are not rewritten.

The implementation still does not admit another native acquisition, select a
new live segment, resolve component continuation or advertise Source3 Ready.

Seven focused child-rotation cases pass in 6.835s. The independent DOM tail is
an actually acquired modeled-native `unavailable` original with sequence2,
while aggregate1 retains its earlier ready DOM. Its genuine tail and all old
native/phase bytes are retained; no SDK/native query or publication occurs
during restore. Unbound old Source3 fences, unresolved child ownership,
missing/foreign child descriptions, same-byte head replacement and a child
inode change during a real original read are refused. A further 25 existing
SourceOwner/fence cases pass in 10.944s.

The private `_closed_snapshot` entry is forced historical and cannot capture
or save. It loads the old Source1/2 body through the existing storage/history
code; it does not read the fenced head as an empty successful source. The
normal constructor still blocks rotating metadata before child construction.
Both copied header body and child profile have explicit separate version1
markers. Source writer2 and native clocks/counters remain unchanged.

The two separate metadata contracts are
`ios-tablet-web-child-rotation` and
`ios-tablet-web-child-closed-header-body`, both writer1/read1. The active
`ios-tablet-web-source-owner` remains writer2/read1,2. Version validation and
the five approved no-build project suites pass (6.82s); no Ready3 or full
source continuation is advertised.

## DOM-only closed predecessor and row 129 reader

`tablet_web_dom_continuation` is the next deliberately historical boundary.
It accepts exactly a complete literal DOM1/2 head with 128 retained rows,
after the nine-child parent has already been fenced and its immutable copy
fully read and validated. It binds the actual current parent signature/hash
and the parent's exact DOM descriptor, including the original header bytes,
observed signature, final record and raw cursor. Archived failed/unknown
queries cannot close under this first narrow profile. No reader replaces a
native floor with the aggregate index or the value 128.

Installation revalidates that same complete source before structural CAS at
the existing DOM head path. The first new child head is Packets3/`rotating`,
with separate `tabletWebDOMContinuationVersion: 1`; there is no ready phase.
The Packet constructor checks this fence immediately after reading its head,
before constructing raw-segment or original-frame stores. Active Packet
writer2 and its literal1/2 record grammar remain unchanged. The separate
fence is not a Packet3 acquisition writer.

Only after this CAS may the immutable closed body be written in the fixed
`tabletweb-dom-closed` namespace. Its own copy device/inode is distinct from
the previous mutable DOM head's documented identity. The body has
`tabletWebDOMClosedBodyVersion: 1` and retains the exact compressed old bytes
and parent binding. The unchanged DOM original store then appends its actual
128 references through the existing block128 manifest primitive, with durable
planned/saved manifest intent before each transition. No frame/raw file is
rewritten or removed. Lost copy/CAS/manifest returns stay owned and fenced;
this packet supplies no retry, reset or manifest-adoption recovery.

Historical replay requires the completed copy and full manifest, compares
every reference against the literal old head and validates every original
row/raw through the existing DOM history. It returns global next row129 and
the original raw cursor, which may differ from129 when earlier replies used
multiple fragments. The native floor is the actual final validated DOM
packet, including an independently acquired input-channel tail beyond the
last aggregate. A historical `unavailable` disposition proves no current
document absence, resource retirement or permission to ignore input failure.

The successor reader can inspect one already retained original at row129.
It requires the exact next row, a new query nonce, nondecreasing original host
clock boundaries, continuous raw-fragment indices and literal DOM native
continuity against the old tail. A higher storage row cannot excuse a native
sequence regression or raw gap. A complete inventory brackets both reads;
same-byte original inode replacement during replay blocks the result.

This is not an active successor journal and does not create row129, capture
new native data, admit another input or unblock the parent. The existing
parent restore correctly refuses its changed child header. Other eight
child successors, aggregate/screen continuation, complete ownership/recovery
and runtime selection remain prerequisites for any acquisition admission.
Feature 7 and the source-complete count 5/14 remain unqualified by this packet.

The initial nine explicit DOM cases pass in 110.130s, including the literal
128→129 boundary, native sequence regression, raw gap, lost successful CAS,
lost saved-manifest return without retry, archived failed query, short prefix,
early constructor refusal and mid-read original inode replacement. After the
parent-copy and in-memory-header guards were strengthened, four explicit
boundary/constructor/alias/parent-copy cases pass in 47.479s. The boundary also
compares the complete private file inventory before/after suffix replay:
original bytes, device/inode, mtime and ctime remain unchanged, with no native,
SDK or publication calls during historical reads. These are eleven distinct
host cases across the two selections, not eleven final-source rerun results.

The bounded fixture creates 128 independent modeled-native query replies with
actual private raw and frame files through unchanged stores. It does not run
128 full Journey captures or qualify production native timing. Its independent
DOM tail is128 while the last aggregate still references DOM1. Row129 is
likewise an explicitly produced fixture original; the production successor
reader only reads it. Existing Packet14, SourceOwner12 and Fence13 cases pass
as a separate 39-case selection in 12.358s after the final source changes.

The new metadata registry entries are
`ios-tablet-web-dom-continuation`, `ios-tablet-web-dom-closed-body` and the
newly used existing primitive's `ios-tablet-web-source-packet-manifest`, each
writer1/read1. No active Packet/SourceOwner writer or native codec is promoted.
The version validator and five approved no-build project suites pass (6.86s).

## Bound DOM successor in historical parent replay

The next metadata codec is DOM continuation2/read1,2. It adds exactly one
`successor` compact original reference, either null or the actually retained
global row129. Closed body1, Packet writer2, SourceOwner writer2 and all native
schemas stay literal. Binding this reference first performs the full original
copy/manifest/128-row replay and actual row129 raw/native continuity checks,
then uses the existing DOM head's structural CAS. It creates no row or raw
file, issues no query and does not retry an uncertain binding. After a lost
successful CAS return, a fresh reader can inspect the exact persisted reference;
another bind call is refused even when supplied the same reference.

Parent historical replay now recognizes exactly this completed child proof.
An unchanged literal child still follows its original path. A changed child
must be DOM with the bound continuation2 profile: its previous literal header
bytes/signature must match the old parent's exact DOM descriptor, its current
head stays identical throughout the read, and the actual closed copy, manifest,
all128 original rows/raws and bound original129 must validate. Changed non-DOM
heads, literal continuation1, unbound continuation2 or incomplete/lost metadata
remain blocked. Original129 inode/hash failure cannot fall back to DOM128.

Only the private forced-historical SourceOwner snapshot can receive that exact
old DOM state. The existing SourceOwner aggregate records are revalidated
against their actual old child references, including DOM1. Parent native and
phase floors therefore remain the actual values from the old aggregates. The
separate returned DOM child tail is the independently validated original129.
All other eight child histories, app sources, parent rows and cross-record
continuity still run literally; complete file census and all nine current
header signatures bracket replay. The public constructors remain fenced and
the parent stays `rotating`, with no Ready, active segment or acquisition
admission. This partial DOM bridge does not qualify the whole Tablet journey.

Four new bound-child-reader cases pass in 77.172s: the full historical parent
path with actual independent DOM129 and unchanged aggregate-native/phase
floors; unbound continuation2 and literal continuation1 before parent snapshot
construction; lost successful successor CAS with exact read-only discovery
and no second bind; and a same-byte replacement of original129's inode which
cannot fall back to128. Complete private original byte/device/inode/mtime/ctime
inventories remain identical across successful historical parent replay and
post-loss inspection. Native/SDK/publication counters do not change during
these readers. The same modeled producers and explicit bounded fixture are
used; this is no physical or production-timing evidence.

A further 46 existing Packet14, SourceOwner12, Fence13 and ChildRotation7 cases
pass in 19.490s. The only registry advancement for this packet is
`ios-tablet-web-dom-continuation` to writer2/read1,2; its immutable closed body
and source-packet manifest remain writer1/read1. The active Packet and
SourceOwner journals remain writer2/read1,2.

An additional explicit full legacy-copy migration case passes in 22.252s. A
literal continuation1 fence with its complete copy and128-entry manifest is
read historically while Parent remains blocked. Binding the actual independent
original129 upgrades only the mutable fence to continuation2. All existing
raw/frame/copy bytes and device/inodes, the exact old copy reference and closed
body1 are unchanged. This gives five distinct new reader/migration cases
across the4-case and1-case selections. Version validation and the five approved
no-build project suites pass (6.80s).

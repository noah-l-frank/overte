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

## Explicit active DOM segment contract

The isolated active component is `tablet_web_dom_segment.TabletDOMSegment`.
It is not wired into ordinary SourceOwner/InstalledAdapter acquisition. Before
opening, the actual source lock and mandatory current source guard must hold;
the complete copied/indexed old128 prefix and permanently bound original129
are read and validated. The same canonical DOM head then advances by structural
CAS from continuation2 to continuation3, with one new
`tabletWebDOMActiveSegmentVersion: 1` body. Original129 is its first unchanged
compact reference. Its actual raw/native/clock floors are retained, not
replaced by the storage ordinal. A lost open return is inspected as the exact
new fenced head, never a lower version or a repeated query.

This active portion holds at most128 references, global rows129 through256.
Its existing Raw/FrameStore namespaces and global1024 bounds are unchanged.
The unchanged 64KiB state-file, packet byte limits, 1.5s query transport bound
and five-second original-file guards remain in force. No signature, native
counter, nonce or original timestamp is recreated or refreshed. A full active
portion blocks row257 before any query; it does not reset to row1 or raise a
capacity. Other segments require separate future qualification.

The ordinary Packet implementation retains literal1/2 header checks and fixed
default start1/empty-prefix hooks. The new class supplies only its explicit
DOM-segment header, fixed start129 and fully replayed immutable predecessor.
Existing `capture`, raw segmentation, issued-before-send WAL, archive,
reconcile and complete-record recovery methods remain the writers. Every
history reopens its actual original prefix and brackets all active reads with
a complete file inventory. The current guard's identity, physical scope and
held lock remain required during construction, reads and saves; no new SDK,
transport factory or authentication selector is introduced.

Pending/issued/failed rows, unsafe raw digests, partial originals and record
write intent remain durably owned in this explicit segment. A failed or
abandoned archived row keeps this first active profile blocked. Archiving an
unknown query does not admit another query or turn it into a successful
observation. A complete actually saved returned record may be recovered by its
unchanged global index and actual inode without another send. Lost CAS returns
cannot reconstruct a missing query result, and reconstruction never resends.

The normal SourceOwner and Packet constructors still refuse the fenced head.
The initial active-segment packet kept Parent historical restore limited to
completed continuation2 and refused active continuation3 instead of returning
its earlier129 tail. The subsequent historical selector is specified below.
Parent/full-feature admission remains unavailable until the other eight
child continuations, screen32→33, aggregate continuation, whole recovery and
retirement paths are qualified. Active SourceOwner/Packet writer2 and native
schemas are unchanged; Feature7 and the5/14 source-complete count do not advance.

The first actual inherited row130 capture passes in29.705s, including durable
issued-before-send query130, unchanged opening originals, reconstruction with
actual native tail130/raw cursor131, mandatory current-guard refusal and
continued public/parent fencing. A subsequent four-case selection finishes in
131.214s with three passing statuses (full128 active capacity, lost successful
open/issued CAS and complete original130 recovery) and one error: its test
expected a raw OSError, whereas the existing SourceReader correctly wraps
that transport error as NativeUIError. Only the assertion was corrected. The
isolated corrected unknown-send case passes in33.962s: query130 and its
original failed clocks remain owned, raw cursor130/native floor129 are not
invented, and archiving uncertainty still blocks another query. The failed
unit fixture cleans its temporary files normally; its full error log remains,
not a retained-original qualification claim. No unchanged four-case repeat was
used or reported as a passing suite.

These are five distinct active-component cases across the three selections.
The128-row capacity fixture directly generates independent modeled original
rows130..256 through unchanged raw/frame primitives, then reopens the actual
bounded head; it does not claim127 production captures or native time evidence.
A separate48-case selection passes in19.786s:46 existing Packet/Source/Fence/
ChildRotation cases plus two pure metadata cases. They preserve literal
metadata1/2 bytes and refuse active-cap growth, raw cursor1026, index reset,
gapped references and a foreign active binding generation. Synthetic metadata
references in those two syntax cases have no original-file/native authority.

Registry advancement is limited to `ios-tablet-web-dom-continuation`
writer3/read1,2,3 and the separate `ios-tablet-web-dom-active-segment`
writer1/read1. Closed body1, existing manifests, source-packet records1/2,
active SourceOwner/ordinary Packet writer2 and native codecs remain unchanged.

## Current historical selector over all nine actual child tails

The next reader boundary inspects the real SourceOwner dispatch instead of
claiming that the active DOM class alone enables whole acquisition. Normal
capture still iterates all nine components under its unchanged NativeClock/
Phase bracket. Besides those aggregate captures, DOM has independent input
reads; Sources/Trace/UIKit/State have toolbar and cleanup reads; Buttons has
app-admission/control reads; Deferred has explicit fault-command reads. Their
tail counts cannot be inferred from the aggregate ordinal. Screen samples
also require a genuine current complete aggregate and current last references
for every child, while retaining their32-row bound.

Two old addressing assumptions prevent direct active-DOM dispatch:
`SourceOwner.capture` derives a child index from its active-list length, and
historical source/operation-cache membership previously used global index-1
against that list. An active segment starts at129 and contains only its own
bounded references. Live dispatch is therefore still unavailable. The narrow
reader adds `reference(global_index)`: ordinary Packet1/2 retains its exact
existing indexing, while DOM3 selects actual old1..128 or active129..256
references. Both Source record interpretation and the existing operation cache
use that same membership check; the cache also pins the reference parser's
identity. There is no new memo, moved I/O or cache-based selector authority.

A forced-historical TabletDOMSegment can read the existing active metadata3,
whole copied/manifests predecessor and complete active native/raw histories.
It never invokes the live current-source guard or epoch sampler. It cannot
capture, save, stamp, archive, reconcile or recover. The private SourceOwner
snapshot accepts exactly that historical class, same physical scope/root,
run/role/fixture/PID, actual lock and bound history/reference methods. The
ordinary SourceOwner and Packet constructor fences remain in place.

Parent historical selection now accepts actual completed metadata3 as well as
the previously qualified bound metadata2 path. The new3 path requires all nine
actual current header signatures and a complete original census throughout;
the active DOM must have no blocked/pending/original-write responsibility, and
every other child's retained rows must be returned. An unknown non-DOM row
cannot disappear behind a newer DOM tail. Literal metadata1 stays blocked;
the prior metadata2/legacy-reader semantics are unchanged. A current active
tail is returned only after actual native/raw validation, never by falling
back to129 or by using a manifest ordinal as a native floor.

Old source aggregates still open their own exact original child references,
so aggregate1 can retain actual ready DOM1 while the separate current child
tail is actual unavailable DOM130. Parent native and phase floors remain the
literal aggregate values. Output stays `historicalOnly` and `rotating`, not
SourceReady or a new image/input admission. Source acquisition, remaining
child continuations, aggregate/screen boundaries and whole retirement remain
open. No serialized field/codec changes or registry promotion are needed for
this reader-only addition to the already explicit metadata3 contract.

The first full all-nine selector case passes in39.143s. Two complete parent
restores in one existing operation-cache scope return identical results and
preserve all original bytes, device/inodes, mtime/ctime and native/SDK counters.
They retain original ready DOM1 in aggregate1 and independently return actual
DOM130 as the current historical child tail. Three boundary cases then pass in
97.076s: a historical segment calls no current guard/epoch sampler and refuses
every write/input/recovery path; no-op history/reference or foreign-PID reader
objects cannot authorize the private snapshot; unresolved DOM query131 blocks
before snapshot construction; and an actually archived unknown Trace2 query
remains byte/inode-owned and blocks the new all-nine selector.

The older active-row130 regression now expects this verified historical parent
readability and continues to require public constructor refusal. It no longer
equates historical visibility with SourceReady. Other default/literal routes
and the existing whole-feature gates are retained.
The final explicit49-case selection passes in58.221s:46 existing Packet,
SourceOwner, Fence and ChildRotation cases, two metadata cases and the adapted
active-row130 case. The four new selector cases pass separately as1/39.143s
and3/97.076s; no whole Journey, native timing or physical-device result is
inferred from these host fixtures.

## Scoped DOM original link during a peer storage rotation

A second child cannot currently rotate underneath the live DOM segment: its
guard deliberately pins all eight peer heads to the original parent
descriptors. Making that live guard accept an unqualified successor would
weaken the existing admission boundary. The next prerequisite is therefore
the isolated `tablet_web_dom_original_link.read` archive reader.

It validates its actual held lock and physical scope, current DOM head,
unchanged parent signature/hash and fully read parent copy, original DOM
capsule/descriptor, DOM copy and manifest, all128 old rows/raws and the entire
completed active portion. It uses the existing forced-historical DOM segment
and global reference/native/raw continuity checks. Pending, failed, unsafe or
partial DOM responsibility cannot produce a complete link result. No current
SDK guard, epoch sampler, query, input or metadata mutation is invoked.

The scope also captures and actually reads the current peer header bytes and
file identities before/after its own original graph. Those comparisons prove
continuity during this read, not that a changed peer is valid or native-ready.
A same-byte peer inode replacement inside the read invalidates it. The result
is explicitly `component: dom`, `subgraphOnly: true`, `peerAuthority: false`,
`historicalOnly: true`, `phase: rotating`. It provides no peer/whole-source
authority. The private prefix cannot save intents or copies; its reader never
escapes, and its lifetime ends in `finally` even after failure.

Live DOM guard and parent all-nine selector retain their existing strict peer
checks. This helper allows a later UIKit predecessor/copy to inspect the
already owned DOM originals without recursive live peer admission. It does
not itself introduce UIKit continuation, SourceReady or a new transport,
serialized codec, cap, native floor or deadline.

Two explicit original-link cases pass in56.567s. A same-byte UIKit head
replacement before entry leaves the live DOM guard and all-nine parent
selector blocked; only the independently validated DOM130 subgraph is returned.
Its original bytes/device/inodes/mtime/ctime and native/SDK counters remain
unchanged. The captured private scope is dead after return and cannot persist
or reread data. A peer inode change during actual original reads and a foreign
binding generation refuse the result without another native query. These
host-model cases do not qualify UIKit, peer readiness or a physical device.

## Closed UIKit predecessor contract

The next isolated child is UIKit, which also receives independent toolbar and
cleanup acquisitions. Preparation requires its actual literal Packet1/2 head
with128 returned rows and no pending/unsafe/record-write responsibility, plus
the completed all-nine historical parent proof. It records exact UIKit header
bytes/signature and the unchanged parent identity before structural CAS at the
canonical UIKit head. The new marker is an explicitly closed
`tabletWebUIKitContinuationVersion: 1`, Packet3/`rotating`; it admits no query
or whole-source capture.

The UIKit constructor first reads the complete current DOM original link. Its
actually observed DOM head bytes/inode are then fixed for this object's I/O
scope, while the parent/copy and remaining seven peer headers retain their
literal guards. A changed DOM identity invalidates that scope; it cannot reuse
the earlier link or create a copy file. This reads no peer as newly native-ready
and does not change the existing DOM live guard.

The existing original store writes the separate UIKit closed body and128-row
manifest with durable copy/manifest intent. Historical replay opens every exact
raw/record and runs the existing UIKit validator across all128 packets. The
native floor is the actual final UIKit packet, including its full objects,
targets, contacts, dispatches and pending-dispatch arrays. A storage cursor129
cannot replace those data or imply release, quiescence or weak-object death.
The old aggregate and every original identity remain retained; literal caps,
global1024 and native/file deadlines remain unchanged. Active UIKit successor,
the multi-child Source selector and SourceReady remain unimplemented at this
closed-only boundary.

The full UIKit128 closure case passes in68.132s with literal old header bytes,
all old frame/raw identities and every object/contact/dispatch/pending-dispatch
field preserved. Its historical native floor is actual sequence128 and its
global next-row/raw cursor129. Two further cases pass in119.933s: lost
successful UIKit CAS retains the exact new rotating head without a lower-writer
fallback or another query, and a changed DOM head inode invalidates the copy
scope before a file or intent is created. The live DOM guard remains blocked
after UIKit storage rotation. These are three host-model cases across1+2
selections, not physical release, quiescence, weak retirement or SourceReady.
The separate48-case Packet/SourceOwner/Fence/ChildRotation/metadata selection
passes in18.924s. The constructor dispatch recognizes only this new UIKit3
closed profile before original/raw store construction; ordinary literal1/2
routes remain unchanged. The two new registry contracts are
`ios-tablet-web-uikit-continuation` and `ios-tablet-web-uikit-closed-body`, both
writer1/read1. Existing generic original/manifests and all native codecs retain
their prior versions.

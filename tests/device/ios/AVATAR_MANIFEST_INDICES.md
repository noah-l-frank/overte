# Original manifest indices during one appearance traversal

The actual held-Avatar endpoint probe reached both native Scene endpoints but
hit its 180-second host bound while publishing the original Scene. A 165-second
stack showed `Scene.joined -> restored_held -> appearance -> frame -> manifest`.
That probe did not pass and its private original graphs remain retained. No
native or operation deadline was increased.

An appearance traversal inside a complete original-read collector now reuses
only its already validated immutable raw manifest index. The existing guarded
`AvatarRecordCache` performs two complete cold decodes, checks original private
file signatures before and after every reuse, restores all actual read
membership, and keeps deterministic missing legacy prefix files absent.
The source binding, role, run, original namespace/schema, exact source root/store,
lock and manifest reference remain part of the key. The reader rechecks every
manifest again before returning from the appearance call.

Every source frame still reopens its actual inode, reads and hashes its original
bytes, compares the in-memory original and performs the unchanged typed native
state/renderer/clock join. No frame, current observation, effect, quiet verdict,
source lifetime, input return or native clock is cached. A slow index reuse still
fails the original five-second file-operation budget. The local index cache is
discarded at function return; it cannot be used for a later observation.

The first collector-only packet kept plain appearance reads on their original
path. An initial benchmark without
a surrounding original-read collector measured extra work in the scoped path
(32 frames: 0.091072 versus 0.110066 seconds; 64: 0.221459 versus 0.262896).
That version was restricted to complete membership traversals, where both paths
must already read the same original prefix files. These initial measurements
remain historical evidence; they do not describe the separate plain memo below.

Fresh host-produced source graphs measured that actual collector path as follows:

| Frames | Original files | Plain collector | Scoped collector |
| --- | ---: | ---: | ---: |
| 32 | 64 | 0.301745 s | 0.118848 s |
| 64 | 128 | 1.360643 s | 0.290504 s |

Both traversals returned identical original frame digests and identical complete
read membership, left every original byte and inode unchanged and issued no
native query. These are component CPU measurements, not a whole-operation or
device timing qualification. The new fixture configures its declared native
State/Renderer/Rig producers coherently before their first acquisition; no saved
packet or source timestamp is rewritten to satisfy the proof.

Seven new continuity/counterexample cases pass, including same-inode manifest
rewrite, original-frame tampering, dangling formerly missing prefixes, foreign
binding/role, changed in-memory data, exit checks and the existing file budget.
The first benchmark plus six ordinary appearance and seven existing cache cases
pass (14 cases in 27.532 seconds). The collector benchmark passes separately in
9.146 seconds. The final eight-case source/actual-normal-effect selection passes
in 4.240 seconds and proves that a genuine normal Avatar recipe has the same
appearance with and without a complete membership collector.

Entry points are `AvatarManifestFrameTests`, `AvatarManifestFrameBenchmarkTests`
and `AvatarAppearanceCollectorTests` in
`ios.self_tests.test_ios_avatar_manifest_frames`. Native/Qt/Rig/SDK producers are
explicit models; Python codecs, original files and normal host recipes execute.
No native compiler, device, simulator, installation or laboratory is used.
The full held endpoint, production worker, canonical metadata retirement and
unchanged complete Avatar journey remain under qualification. Avatar capability
admission remains closed.

## Separate plain traversal memo

The second fresh held-terminal probe also reached the original native endpoints
but timed out at 180 seconds. Its diagnostics counted at least 225 appearance
traversals, all with `collector=False`. The collector-only path above therefore
could not improve that actual prefix. Its retained original graph and diagnostic
log are described in [canonical routing qualification](AVATAR_CANONICAL_ROUTING.md).

`_AppearanceFrames` now has a distinct plain-index memo. It does not activate an
original-read collector or enumerate old prefix snapshots. Cold actual manifest
bytes are decoded twice around their private file signatures; warm reuse checks
that same original index's inode, mode, ownership, length and mtime/ctime before
and after copying its already typed entries. Each call still reads and hashes
the actual selected frame and repeats its unchanged typed source check. The
scope freezes source binding/run/role/store/namespace/manifest context and actual
private parent identities. It also fixes collector mode at its first actual
read; the exit cannot silently switch to a different original-read boundary.
A final index check precedes return. No frame bytes,
native clocks, effect or lifetime verdicts are memoized.

`avatar-manifest-both-modes-20261026.log` records **30 passing explicit tests in
37.345 seconds**, including the existing appearance and raw-record cache cases.
Fresh 32/64-frame graphs measured both modes:

| Collector | Frames | Original files | Original traversal | Local index memo |
| --- | ---: | ---: | ---: | ---: |
| false | 32 | 64 | 0.095413 s | 0.087552 s |
| false | 64 | 128 | 0.232721 s | 0.176964 s |
| true | 32 | 64 | 0.301842 s | 0.125078 s |
| true | 64 | 128 | 1.352141 s | 0.303135 s |

For every row, spies around actual successful frame reads and private index
reads observed identical file-path sets. Complete collector membership and
resulting frame digests were also identical. Every original byte/inode stayed
unchanged and historical replay issued zero native queries. These bounded
component measurements establish a modest plain-path improvement; they do not
establish that the whole retained end meets its deadline.

`AvatarPlainManifestFrameTests` adds plain-mode tampering/budget/context and
actual parent-replacement negatives. Collector tests explicitly run inside a
collector. A plain traversal continues to ignore older prefix files, matching
the original read set; only complete collectors admit and guard those prefixes.
The independent original-frame and typed-state checks still run in both modes.
After adding the immutable-mode guard, all 18 affected explicit manifest,
both-mode benchmark and actual normal-appearance parity cases pass in 17.838
seconds (`avatar-manifest-mode-final-20261026.log`). This includes the added
mode-switch negative; the unchanged record-cache suite was not repeated.

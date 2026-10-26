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

Plain appearance reads retain their original path. An initial benchmark without
a surrounding original-read collector measured extra work in the scoped path
(32 frames: 0.091072 versus 0.110066 seconds; 64: 0.221459 versus 0.262896).
The optimization is therefore restricted to complete membership traversals,
where both paths must already read the same original prefix files.

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

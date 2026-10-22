# Complete original Chat source history

ChatSamples v4 retains each complete original primary/peer/view/lifecycle bundle
in a separate immutable, numbered private file. Its root contains the original
run, role, both candidate/process bindings, VR requirement, acquisition phase,
revision and ordered SHA256 manifest. Each child binds that same scope and its
exact index to the existing strict compressed-original codec. All canonical raw
frames together still have the original 16-MiB/512-frame bound; every private
file remains below 64 KiB. No old sample becomes a fresh measurement.

The root's original reading intent is durable before any native query or child
write. The original complete child is durable before the corresponding ready
manifest. Failed/uncertain writes retain reading intent and any original child;
a new object cannot adopt that interrupted acquisition. Deleted roots, orphan
children, missing/reordered/foreign/changed frames and nonprivate files fail
closed. No truncate, migration, overwrite or discard operation exists. Old
v1/v2/v3 journals remain unresolved and are not adopted as v4.

Reconstruction checks every original compressed frame, scope, manifest hash,
order, nonce, native cursor and continuity rule without querying a source. Actual
inode, nanosecond modification/change times, private permissions, owner, link
count and size remain pinned for every child; the live owner checks these before
new native queries and after its final durable write. Original source locks,
whole-acquisition timing and the final independent native wall clocks retain
all existing requirements. Separate primary and actor histories remain distinct.

Focused host tests retain 355 distinct original bundles, each containing 256
changing native pose rows, demonstrate that the previous flat 48-KiB compressed
field cannot hold them, reconstruct every byte without new source queries and
then demand another fresh full bundle. Fault cases cover original files,
interrupted writes, old versions, the total raw bound and a frozen host clock
with a late native-clock jump. Mixer recovery preserves every interrupted native
child while restoring only its independently owned process. These synthetic
source tests establish component behavior; full Chat composition, independent
publication, cleanup and device qualification remain required.

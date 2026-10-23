# Strict warm consumption of original Chat cleanup observations

`ChatCleanupConsumption` version 1 binds one exact warm `ChatCleanupBaseline`
and one exact common `Journey`. Register its original `callback` as that
Journey's `after_cleanup_baseline`, attach the Journey, and call `begin()` after
the actual cleanup sources are available and before acquiring their rows.
The baseline's original private store records this intent. Existing roots or
orphan chunks cannot be adopted. The baseline's separate `run()` is then
disabled; no second internal baseline can qualify an external result.

The callback accepts only the exact immutable bytes issued by that same
Journey after its original common cleanup wait. The engine pins the original
phase and samples when the wait returns. Caller-created windows or later
in-memory mutations cannot invoke the callback. Only `execute()` supplies the
actual input-sequence success flag; a direct cleanup wait emits
`sequenceSucceeded: false`. Cleanup sources may still need closure after an
input failure. That false field is retained and cannot qualify a complete
external journey.

The consumer matches every consumed primary sequence, epoch, state, resource
and lifecycle field to the original primary observation. It matches each
independent received witness to the exact actor publication and requires the
current original cleanup activation, ticket and barrier. Copies and physical
CAS work precede the final checks against the same original native clocks.
It stores the original receipt header and SHA-256, and the actually consumed
rows with their primary/actor original hashes in the baseline's immutable
chunks. Those rows reconstruct the exact original receipt bytes. Only then
does it run the existing actor and primary source seals. It does not restart,
close native IPC, retire journals, close host handles, or grant a capability.

No cursor is translated. The current private primary source starts at one;
the current cleanup actor follows the private 26-row witness. A pre-existing
external primary/actor cursor cannot be replaced with those private counts or
with caller offsets. A real full external adapter needs a durable cursor and
repeated active-phase actor publications before this consumer can join its
cleanup. Public Chat RPC routes, cold ownership and stereo qualification remain
unimplemented. The optional archival baseline extension already preserves
these complete source roots and chunks; older private baselines acquire no
invented external-consumption metadata.

`self_tests.test_chat_cleanup_consumption` checks actual source owners, physical
journals, independent received publications, the unchanged common three-second
wait, its original hook emitter, source seals and a frozen-host/native-clock
failure. Native/input/clock producers are explicit seams. The positive does
not execute a full external 25-action Journey: its receipt explicitly records
`sequenceSucceeded: false`. Separate shared-engine tests exercise the real
`execute()` hook ordering and success/failure flags against the boundary model.

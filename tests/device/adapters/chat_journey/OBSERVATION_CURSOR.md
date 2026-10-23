# Warm original Chat observation cursor

`ChatObservationCursor` version 1 starts at zero before the first query of an
exact unused initial `ChatObservationOwner`. Every read acquires a new original
sample and records an immutable reference to its local source sequence and
source-row digest. Its global sequence counts those actual queries. It never
uses a fixture phase count, an old 26-row witness, or a caller offset as a cursor.
The original source sample retains its local sequence; the separately journaled
public sample carries the global sequence. Every other measured field is the
same original field. No old sample is returned to satisfy a new read.

The cursor can select an exact unused active owner, then an exact unused cleanup
owner. They must retain the same source-reader object, binding, role, flow,
private parent and actual source-lock objects. Initial/active share their exact
compiled-script owner; cleanup retains its original successor chain. Selection
has a durable intent. The first active sample must prove the original native
absent-to-owned cache birth and view/keyboard continuity. The first cleanup
sample must prove actual retirement of those same native caches, PID/domain
connection birth, keyboard and lifecycle continuity. No selection creates an
input, cache, script or desired state.

Ready output is stored before return. Physical chunk identities, root stamps,
cached source rows and exact JSON types are checked; tuple/subclass aliases do
not preserve admission. A query outside this cursor's own history cannot be
adopted. Lost source or cursor completion, changed physical or cached originals,
unknown rootless chunks, cold roots and future caller cursors fail closed.
There is no retry, deletion or cold reconstruction API. The original source
checks, copied output, contract validation and successful lock release all
precede the final checks against the same original native clock functions and
the unchanged 1.5-second age bound. No fresh HTTP response retimes native facts.

Pico's private `_chat_observation_cursor` factory checks the fixed initial
observation path, original role/credentials and current binding. Its fixed
stores and rootless chunks are included in the generic cleanup admission guard.
This does not connect a public RPC route, actor publisher, external Journey,
source seal/archive finalizer, cold host lifetime, or stereo capture. The
existing private 26-phase dispatcher/witness remains separate.

`self_tests.test_chat_observation_cursor` exercises actual source owners and
physical journals with native/V8/widget/input/clock seams. Initial repeated
queries and ordinary Open through the existing child owner are covered, along
with lost completion, external source-query adoption, cached mutation, exact
types and frozen-host/native-age failures including lock release. A separate
source continuation test uses actual native-cache retirement owners and new
cleanup sources after explicitly simulated metadata for the remaining 24 input
rows. It checks the global/local cursor boundary across all three stages,
without qualifying those 24 target effects, full restoration or a whole feature.

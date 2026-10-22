# Original AvatarApp entity ownership

`AvatarEntityObservation.h` records the actual successful Avatar-hosted entity
return from `EntityScriptingInterface::addEntityInternal`, after its original
local-copy and packet-queue path. It separately records each actual immediate
own-avatar deletion, after the product deletes that entity and clears its
actual Avatar entity data. It does not create, rename, select or delete an
entity, and a test query cannot supply entity identifiers or caller metadata.

The original V8 invocation context retains actual manager/load identity, top
code identity, invocation sequence/time, actual script caller chain and the
Avatar module code identities handed to the real evaluator. Capture is gated
by E2E+iOS and `--testScript`. Relevant event history is bounded and immutable;
overflow or unavailable provenance is explicit. This source remains separate
from Renderer version 4 and does not change that reader's legacy meanings.

`avatar_entities.py` reads `feature-ios-avatar-entities.json` through the same
closed HTTP/AFC nonce transport and independent native clock path as the other
Avatar sources. Its strict event parser preserves both original process birth
and ledger birth, original returned IDs, original code, original clocks and
event prefixes. Recursive deletions may share a real single native invocation;
two creations cannot reuse an original returned ID.

The ownership join first selects a genuine new original returned ID after the
actual input barrier, then joins that ID to the separately read whole-tree
inventory and loaded renderer. A matching URL alone cannot supply a creation
event, adopt an already existing entity or turn an ACK into loaded geometry.
Original native caller/code must match the independently read live manager and
separately trusted candidate module manifest. The original AVATAR_SELF_ID is
retained as received; resolution uses the separately observed actual self ID.
Actual Hips index, parent, model URL, loaded geometry and scene presence remain
renderer requirements.

Host verification includes strict source/caller/code/history counterexamples,
existing-ID and missing-return refusal, loaded-model/Hips failures, true parser
and HTTP/AFC dispatch, actual Node probe nonce/unavailable behavior and source
ordering checks. Native code has not been compiled or executed on a device.

This is a source ownership prerequisite. The complete action owner still must
retain IDs before uncertainty, preserve unowned resources, coordinate genuine
peer and GPU evidence, and prove complete product/provider cleanup.

`IOSAvatarSources` now writes version 2 with an explicit version-2 acquisition
group containing this sixth typed source and its own original acquisition
clock/hash. It still reads version 1 without inventing entity events. Existing
immutable version-1 groups and source floors survive migration; only a new
actual read can add the new source, and a subsequent group cannot downgrade it.

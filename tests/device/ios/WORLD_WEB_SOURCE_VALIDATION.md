# Original clock floors and bounded transcript validation

The Places model and World Web transcript readers accept an optional
`native_before_floor` containing an actual, retained native feature observation.
They copy and validate its complete original packet and process identity before
issuing a source query. This replaces only the ordinary before-clock query;
terminal clocks are newly acquired. Both the source acquisition and the interval
from the retained floor to the final clock must remain below 1.5 seconds. The
ordinary calls retain their previous two and three clock acquisitions.

This argument is a before bound, never a current time. Its enclosing owner must
retain the actual raw original and acquisition, prove that they belong to this
acquisition, and include them in historical validation. A valid native packet
alone does not establish that outer ownership. Places records the digest of the
copied floor in its acquisition metadata. No wire schema changes.

`world_web_source.validation_round()` reuses at most 256 successful pure
transcript validations within one synchronous context. The key includes the
actual packet, command, PID and predecessor. Freshness is checked again on every
reuse. Mutated bytes, a different predecessor or a later epoch cannot reuse a
proof. Nested rounds share the entered context; leaving the outer round resets
it. This stores no original files, acquisition results, returned objects or
transport responses, and does not remove durable writes or ownership guards.

Six focused host tests cover both original-clock paths and pure validation
reuse over the committed native/model/transcript fixtures. They reject foreign
PIDs, old floors, mutated packets and warm-proof freshness failures. Existing
source/model regressions also run. These are modeled source tests, not native
compilation, device results or a physical timing acceptance. A positive short
CPU input sequence has not established reliable timing for the full 19-step
World Web journey; that whole adapter remains incomplete.

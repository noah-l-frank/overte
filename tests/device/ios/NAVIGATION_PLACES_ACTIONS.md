# Durable scoped Places actions

`navigation_places_actions.NavigationPlacesActions` now owns whole calls to the
eight [ordinary Places recipes](NAVIGATION_PLACES_INPUTS.md). It requires an
already owned open page; initial open/close, error, restart and scene cleanup
are still obligations of the unfinished whole Worlds coordinator.

One fixed private record binds the original candidate/process, run, provider
instance/configuration and source lock. Before fixture reads or normal input it
reserves the actual action call as `checking`. The genuine original fixture phase
must match the actual supplied ticket, verb and input fields before `issued`
is saved. A mismatched genuine phase stays retained as a failed checking attempt.
No requested phase or fixture acknowledgment becomes product evidence.

Each actual normal input checkpoints its original token reference, source
packet, entered value and same original action call before transport. Native
input/observation/time counters continue across steps and acknowledged calls.
The final observed UI original is retained separately from all preceding intents;
an action acknowledgment cannot be reconstructed without that original history.
The runtime supplies an original native UI floor, so a new page flow cannot
silently adopt a same-instance input-counter rollback.

An uncertain checking/issued call blocks both its old ticket and a different new
ticket after reconstruction. A failed final result write leaves all actual input
intents owned without resending. A repeated acknowledged latest call returns
only its old delivery acknowledgment without more UI reads or inputs. Provider,
candidate, phase-prefix and source-counter replacement/rollback are rejected.
The wrapper holds the existing source lock and shares a bounded 30-second call;
it advertises no complete capability and does not delete ownership records.

This is the durable owner for the existing open-page scope. A whole Worlds
coordinator must separately own page creation/replacement, actual rendered
arrivals, saved bookmark outcomes, missing lookup and dismissal, process-death
qualified restart transfer, independent publication and repeatable quiet cleanup.
Cross-process/page transitions cannot bypass retained partial responsibility.
Native compilation and devices remain unverified.

Host tests exercise actual private atomic journals, genuine loopback fixture
phases and real Python normal-input codecs with modeled Qt/native state. They
cover multiple actions, duplicate delivery acknowledgment, phase mismatch/loss,
lost final results, ignored input, source/provider replacement and history
rollback. They do not establish actual iOS feature functionality.

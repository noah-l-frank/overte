# Original Chat cleanup admission v1

`ChatCleanupAdmission(flow, private_store).admit()` admits only the actual active
cleanup activation following the complete original 26-row baseline/action
prefix. The original `ChatFlowInputs` journal and RAM history must match, every
row must be consumed, and its last original phase must contain all 26
activations. The enclosing parent still qualifies the actual Dispatcher/input
and native model proofs; this component supplies phase ownership, not target
effects, resource release or a cleanup verdict.

The new independent `PhaseFixtureReader` requests the real current phase. It
must contain exactly the unchanged 26-row prefix followed by a 27th
`cleanup`/empty-input activation. No controller, UI, ACK, desired cleanup state
or caller-supplied ticket can establish that phase. Admission records its own
durable `reading` intent before the request and retains the original phase plus
the digest of the completely consumed original input journal. A lost receipt
remains retained. Warm owners cannot repeat admission, and construction refuses
an existing journal. No journal is retired here.

Initial/final CAS, copies and final original phase/host clocks remain inside the
same 1.5-second window. A newly generated phase response cannot erase an earlier
slow CAS. The admitted historical packet is only the fixed prefix/ticket
authority; it never replaces a fresh phase query at an input boundary.

`ChatPhaseFence(flow, cleanup=admission)` creates a separate fence with its own
stable callback ownership. It requires that exact flow/admission object and
rechecks the unchanged original input/admission journals before every original
read. Each actual pre-transport hook still queries the independent current
phase, requires the exact original cleanup ticket and full prefix, and preserves
the original child CAS clock anchor. Phase replacement or fixture retirement
refuses input. Original controller `intent`/`before_publish` callbacks retain
their pure host-only restriction. The ordinary Dispatcher fence still requires
an issued action and is never relabelled as cleanup or silently replaced.

Six new component cases use the actual fixture journal, phase reader, source
locks and CAS code. Fully consumed input-row references are explicit synthetic
metadata seams; these tests do not claim the 25 target effects or native
cleanup. They cover original cleanup admission without Qt/input, incomplete
flow, wrong phase/changed prefix, replaced/retired cleanup, slow initial/final
CAS under either frozen clock, and a lost durable receipt. All six ordinary
phase-fence cases also passed. The first combined run was red on the lost-receipt
test's exception-context expectation; after correcting that test, its targeted
rerun passed in 0.909 seconds. No exception, freshness bound or default route was
weakened.

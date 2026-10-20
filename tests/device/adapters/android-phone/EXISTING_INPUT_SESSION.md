# Existing-session input admission, version 1

`PhoneAppiumAdapter.existing_input_session(selector)` admits ordinary feature
input using one already existing SDK session. It is a context manager for the
full Phone coordinator, alongside the existing source-lock and ownership
transactions. It neither observes a feature result nor advertises a capability.

Entry requires the existing private session, an integer generation, current
local target fingerprint, SDK liveness and independently verified installed APK
bytes. The private in-memory pin retains the selector, actual SDK session ID,
actual generation, actual fingerprint and original installed identity. No
requested effect, desired state or expected native count is stored or returned.

Inside the context, all nested `ensure_session` calls use the non-repairing
`existing_session` route. A dead/missing SDK cannot fall back to the parent
session creator, delete/rewrite its journal, reinstall, activate or launch the
app to repair admission. Normal explicit UI/file input is still permitted
through its existing guards. Direct read-only admission also respects the same
pin. Changed session IDs, endpoints, targets, generations, typed metadata or
installed bytes fail before further input. A Boolean cannot replace an integer
generation in either the current record or the pin.

Nested contexts may only reuse that original selector/session. Foreign selectors
are rejected before state-path/SDK lookup. Successful exit repeats current SDK
and installed-candidate proof. Failure retains the owning normal-input journals
and propagates the failed input; no success is manufactured and no input is
replayed. The pin is always released on exit, so ordinary bootstrap admission
outside this explicit scope retains its existing behavior. This changes only
one Phone adapter instance, with no global SDK or other platform mutation.

An explicit normal application stop/launch may use the same live SDK session.
That does not prove a new product process: original kernel exit, native birth,
actual lifecycle counters, pending-manager/engine/effect absence, unchanged
original files and the existing handoff remain separate requirements. Lost SDK
returns keep the existing one-send restart phase. A later call can proceed only
through those original proofs, without stop/launch or staging replay. Losing the
SDK itself blocks the flow; the scope does not create a replacement SDK session.

The scope retains the existing SDK transport limit and each input/getter's
bounds. The full coordinator must hold the Script source lock around its
ordinary input, persist input intent before delivery, and preserve the outer
runner deadline. This admission layer is not an exclusive source lock, durable
run ledger, restart-history migration, independent publisher or cleanup proof.
No SDK acknowledgment substitutes for fresh feature observations.

Twelve new Phone host cases cover actual normal file-picker input, explicit
one-send restart and original native/kernel handoff, lost stop acknowledgment,
dead SDK, target/endpoint/session/candidate replacement, Boolean corruption,
direct read-only admission, nesting, retained failed input and exit restoration.
The existing mandatory Phone runtime owner runs them in `test_feature_adapters.py`.
Boundaries are synthetic; native code remains uncompiled and devices untested.
The full nineteen-step coordinator/file cursor, explicit role-history restart
handoff, independent publisher and verified complete cleanup remain pending.

# Avatar primary control and checkpoint ordering

The normal Avatar primary keeps its GET-only, peer-facts-filtered fixture
client. An explicitly configured `authorityControlRoot` supplies a separate
capability for the existing session-binding and authority-revocation POSTs.
The runner prepares it through the existing HTTPS fixture after registering
the run and before preparing the adapter. Set
`OVERTE_E2E_AVATAR_PRIMARY_CONTROL_HANDOFF_ROOT` to the same private directory
used by the primary configuration.

The issuer saves its request before sending. A missing return is recovered
only by GET of that original request; it never sends another grant request.
The server binds the grant to one run, the primary role and two purposes.
Each purpose is consumed before the provider call, including an uncertain
provider return. Recovery uses existing read-only status instead of repeating
the effect. A retired run cannot use its retained grant.

The primary's cleanup ordering reads the existing actor-private checkpoint
and published phase original under the paired source locks. It validates the
original actor binding, run, phase, ticket, body, publication and unchanged
inventory. The returned receipt contains ordering metadata, without tokens or
peer facts. General fixture journal access remains redacted.

The implementation is in
[the fixture handoff](../feature_journeys/avatar_primary_control.py) and
[the adapter receiver](adapters/avatar_primary_control.py).
The five new wire/document families read version 1 only. Existing Reader
component owners retain their default path; live GET-only primary owners
require the explicit control profile before state creation or native input.

## Host verification

Seventeen selected checks passed: six actual TLS authority/recovery checks,
two primary-owner checks, one paired checkpoint ordering/tamper check, five
existing TLS account checks and three existing session-admission checks.
The runs retained 431 original files across 25 genuine temporary roots.
All 7,814 source/launcher pins stayed unchanged. Actual host Node processes,
streams and fixture threads completed their original cleanup.

The frozen local run packet is
`.ios-host-tmp/avatar-primary-control-explicit-budget-root-preparation-20261029`.
The earlier preparations remain unchanged, including the detected missing
budget-decision field corrected before execution.

This qualifies the scoped control and ordering components. Avatar capability
activation, the full installed journey, terminal worker process exit and
paired end remain open. SDK, Qt and native sources in owner tests are declared
host models. No native build or device test was performed. The complete-area
count remains 5/14.

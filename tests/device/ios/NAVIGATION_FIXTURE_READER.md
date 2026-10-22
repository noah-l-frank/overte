# Read-only iOS navigation fixture attachment

`NavigationFixtureReader` attaches to an existing registered Worlds/navigation
run through `Client` or the existing `AdapterFixtureClient` role. It never
registers, activates, closes, mutates or publishes a run. It does not assign
another run/area to a client or borrow independent peer entries. Adapter access
continues to require the existing separate read-only-role handshake.

Attachment retains the actual provider instance and three original input
configuration fields. Later reads must preserve these source identities and the
client's original URL/run/area context. The future whole owner must separately
join those input revision/protocol/origin fields to its installed native sources;
fixture readiness does not establish installed-code identity.

A read obtains the nonce-bound shared phase journal, original navigation
provider status and opt-in scene source, then another nonce-bound phase journal.
Original histories remain append-only. The active ticket and complete activation
history must agree across this bounded read. A phase crossing raises
`NavigationPhasePending` without publishing a new sample or issuing any input.
A retired run raises `NavigationRunRetired` with its original retired phase;
passive original source reads remain available for cleanup checks.

Provider clocks retain original integer milliseconds, while phase clocks can
retain fractional milliseconds. The bracket allows their original one-millisecond
quantization without rewriting either source. The 1.5-second host-monotonic
validity window and server-clock freshness checks are separate from iOS native
clocks. No server/host time is relabeled as native freshness.

The version-1 read record preserves both phase originals, directory and scene
sources, their immutable digest, actual input ticket/stimulus, original provider
read epoch and host-monotonic span. It contains no product location, bookmark,
renderer or peer success. A disabled/missing scene profile is unavailable.

Actual short loopback tests exercise the existing adapter-only credential,
phase changes during reads, repeated original histories, source replacement,
retirement, foreign client scope and refusal to represent runner credentials as
adapter-only access. No device, SDK creation, compiler or build is involved.
The durable Worlds owner, actor and full journey still remain to be integrated.

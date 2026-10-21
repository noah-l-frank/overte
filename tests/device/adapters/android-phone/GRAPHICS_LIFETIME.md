# Original Graphics fixture and Web lifetime, version 1

`GraphicsFixtureReader` and `PhoneGraphicsLifetime` are internal, read-only
components for the future complete Graphics adapter. They do not advertise any
`feature.graphics.*` capability. Scripts and Authentication remain the only two
complete Phone area implementations. All physical clients are untested; native
instrumentation remains uncompiled.

## Existing fixture attachment

`GraphicsFixtureReader(client,run,epoch_ms=...)` attaches the role's already
credentialed shared `Client`. It never registers or activates a fixture, obtains
credentials, mutates account state, or supplies requested settings as results.
The canonical fixture origin, run, area and provider birth are pinned. Existing
client scope/history cannot be silently replaced. A deliberately closed Client
is admitted only to observe the original inactive provider, including an actor
attaching after retirement.

`read(previous_status)` brackets the original active stimulus and journal read
with two fresh provider requests. Both responses must retain the complete
append-only activation/socket-response history. Provider, active stimulus and
journal must agree on the actual ticket; the original journal epoch cannot
precede its activation or follow the final provider capture. The returned
`afterEpochMs` is that journal read barrier, not an activation time or measured
native state. Later product acquisition must obtain new originals after it.
The closed common Graphics action grammar validates actual stimuli. An independent
sampler may supply a newer provider floor only through validated original history
prefix continuity; a stale caller floor cannot shorten the retained history.

`GraphicsPhasePending` reports a real ticket race without relabelling anything.
`GraphicsRunRetired` carries the original inactive provider packet and does not
query a removed active endpoint. Malformed/foreign/stale/unhealthy originals,
clock regression, changed provider history/origin and reused read nonce fail.
The complete coordinator must catch expected phase waits outside the held
source-lock context, as in the existing Authentication coordinator.

## Separate role and process ownership

`PhoneGraphicsLifetime(adapter,selector,source,role,stage,held_lock,...)` requires
role `primary|actor`, process stage `0|1`, the actual installed/process/session
binding and the held existing `phone-script-sources.lock`. All product sources
use read-only existing-session factories. There are no SDK repairs, functional
inputs, direct Entity writes, navigation, cancellation, browser destruction,
fixture retirement or GPU image requests in this component.

The private `phone-graphics-<role>-<stage>-lifetime.json` envelope is version 1.
It binds run, canonical fixture origin, original provider birth, role/stage and
full installed/process context. Its compressed, hashed payload retains each
accepted source cursor before another request, original active ownership proofs,
the immutable original user scene and all quiet-window attempts. Lost/ignored
writes or foreign replacement cannot produce a successful observation. Source
births/cursors/clocks and original histories survive reconstruction. Limits are
eight active proofs, eight quiet-window attempts, 64 samples per window and 256
completed source groups; quotas fail closed. Existing private state bounds apply.

Each group contains only original `providerBefore`, native subject/view,
complete native scene-load inventory, native/Android Web inventory and
`providerAfter`, plus its local journal sequence. Original clocks must be ordered
and span at most 1,500 ms. Final host freshness and a separate monotonic elapsed
floor include the initial provider read; a frozen clock cannot hide slow input.
Subject, scene-load and both native/Java Web histories advance independently.
Every original nonce remains attached to its source; packets are never retimed.

## Observe ownership before claiming its release

`observe_active()` has a 15-second whole-call budget, while the completed group
still must meet the stricter 1,500 ms freshness bound. It independently requires
all seven actual fixture UUIDs/properties, an actual completed controlled scene
socket response preceding the subject observation, a committed current native
scene with every traced request/handoff lease drained, and the actual live world
Web source/document/grant/page matching the freshly observed marker entity.
This proves original ownership and authority, not GPU pixels or visual effects.
The separate original image/trace components remain mandatory.

`wait_released(original_subject)` requires this same role/stage to have observed
actual active ownership first. The supplied immutable original subject must be
the complete actual version-2 user scene retained by the scene owner, with its
original process identity. The complete coordinator must bind that argument to
its separately verified Scene archive; this component does not invent or acquire
a replacement baseline. An explicit restart must retain the old stage separately
and prove actual old-process exit; it cannot relabel old originals as new-stage
lifetime evidence.

Every release sample requires both provider reads to be inactive, all seven
fixture UUIDs actually absent, the original user scene resource/feet/view/scale
restored, the declared partial foreign spatial inventory preserved, a current
committed scene with every traced native request/handoff drained, and the
[original Web runtime release assertion](../../native/PHONE_WEB_RUNTIME_OBSERVATION.md).
An absent entity or an acknowledged Go input cannot replace those sources.
The spatial scan remains explicitly partial, and the Web source does not claim
global browser/network or all-Qt-callback enumeration.

## Independent quiet window and final retirement

The component samples every 250 ms, subject to source latency, until at least
three independent groups span three seconds on **both** the monotonic clock and
the original provider epochs. The whole invocation is bounded at 20 seconds.
Each accepted sample is durable. Any live remnant, missing source or provenance
error fails that attempt immediately. A reconstructed/retried call retains the
old incomplete attempt and source floors, then begins a new full quiet window;
it cannot combine separated intervals or reuse old samples as current facts.
A successful window yields the original journal with phase `released`.

`archive(...)` validates historical originals without SDK/clock/input access or
new measurements. It verifies each group, original source continuity and every
completed quiet window. It returns historical state only. The successful journal
is deliberately retained: the complete Graphics run owner must first persist its
exact original archive in a recoverable whole-run retirement plan, independently
verify the other role/stage/image/scene/settings/restart records, then discard
only the exact owned journal and separately observe its absence. No general
cleanup fallback silently removes it. General Phone cleanup refuses either
role/stage lifetime journal, even a `released` journal.

## Host verification and remaining work

Seventeen fixture-reader and nineteen lifetime cases use the actual shared
fixture/journal reducers, original source-reader implementations and private host
journals behind explicit synthetic HTTP/native boundaries. They cover original
ownership/release, all independent source floors, live Java/callback/scene
remnants, late remnant recovery, frozen clocks, initial provider latency, wrong
role/stage/binding, changed originals, lost/ignored writes and pure archives.
The Phone wrapper separately checks general cleanup across all four journals.
These simulations verify test logic only. Full independent role/GPU/pixel
composition, normal action orchestration and recoverable whole-run retirement
remain required before registering the complete Graphics triple.

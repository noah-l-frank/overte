# Independent Chat receiver v1

`independent_chat_receiver.IndependentChatReceiver` is a read/ownership component
for the separate witness process. It does not implement a full Chat actor or
feature adapter. Actual process/code-bound actor transport, normal primary UI/
storage reads, peer send/distance, controlled MessagesMixer lifecycle and the
private publisher remain required. The existing `domain_peer_agent.js` is still
only avatar motion/heartbeat and cannot stand in for this receive ledger.

## Original native actor source

`Agent` creates/starts a real `MessagesClient`, requests MessagesMixer and exposes
that same object as the ordinary `Messages` script global via ScriptManager.
The default-off E2E reception tap already observes original `messageReceived`.
Its existing `featureChatObservation` method is now Q_INVOKABLE and marshals a
script-thread call to the real MessagesClient owner thread. Use the actor control/
poll path rather than invoking this blocking read from a native receive callback. It refuses an absent
`--testScript` opt-in or stopped owner thread. The closed read/inspect/retire
protocol and source v1 result are unchanged; the method never sends or subscribes.
The Interface Test wrapper continues to use the same native producer.

A dedicated `OVERTE_E2E_FEATURE_TESTS` Assignment Client accepts the opt-in
`--testScript` flag and propagates it to monitored children. For this program it
is a source opt-in, not an Interface script-file argument or a replacement
assignment. Default builds do not accept the option or expose the method. No
Assignment Client, domain stack, build or device was started here; native code
is source-reviewed only and remains uncompiled.

The native bridge permits a future authenticated/private owned Agent transport
to acquire its own real reception cache. It is **not** permission to trust an
unauthenticated HTTP heartbeat or a submitted JSON object as an Agent result.
Bind actual actor executable bytes/source/PID/start identity, actual assigned
script code and private endpoint ownership before constructing the receiver.
Do not expose actor credentials through script URLs, command lines or logs.

## Pairing and acquisition

The witness owns one `OwnedChatCapture` for the peer and a distinct
`NativeChatObservation` reader for independently inspecting the primary cache.
It must query the primary itself over its own bound transport, never receive the
primary adapter's normalized sample as an observation. Primary/peer bindings use
the existing private source/artifact/process/session/target context. Unbound UI
component mode must be explicitly selected and cannot produce product acceptance.
The receiver checks actual PIDs against those bindings, distinct target
fingerprints, native birth instances and native self digests. Matching display
names, outgoing requests or a second label on the same target are insufficient.

Before pairing, the primary must already own an active run cache. Peer scope
creation uses its existing persisted source/run ownership and native absence
preflight. The first two actual sources must observe the same nonempty native
MessagesMixer identity. Original opened epochs and per-process sources are
retained in the private receiver journal; future reads cannot replace them.
Mixer replacement requires both original sources to have actually observed its
absence before a fresh matching node identity can be adopted. Absence is recorded
from reads, never from a requested network operation. Failed pairing/journal
write preserves the peer cache owner's recovery intent.

Every sample performs new original primary inspect and peer capture requests and
requires the whole acquisition to finish within 1.5 host-monotonic seconds.
Original native epochs remain in their own clock domains and are not relabeled
with host time. Each existing reader additionally enforces request/sequence/
clock freshness, immutable overlapping history, pinned native identity and no
dropped events. Slow/unavailable or foreign sources are errors, never empty
receiver results. Native message reception histories may retain old events;
new cache reads do not rewrite their original event time/order.

`peerMessages` contains only primary-sender events actually received at the
separate peer, with native `localOnly:false`, in original global reception order
and multiplicity across both Local and Domain payload channels. Peer self echoes,
local-only fallback, foreign senders and outgoing ACKs never count. The returned
primary/peer original documents are private component evidence; only independently
measured closed feature facts may enter the public witness projection. This
component does not claim that either UI rendered an incoming packet.

## Retirement and checks

Retire only the actor's owned peer cache. Its existing owner requires actual
retirement plus two independent empty/fenced inspections before dropping intent;
the receiver then performs another fresh inspection and matches its original
peer before discarding its own journal. A partial cleanup with an already removed
peer-owner sidecar still must prove the actual original retired source. The
primary cache/UI remains owned and retired by its own adapter. Any failure or
foreign journal preserves unresolved receiver ownership.

Nine host cases use separate synthetic native boundaries and real private files.
They cover order/multiplicity/channels, self/local/foreign echoes, same target/
source/self or wrong mixer, actual mixer absence/replacement, missing cache/read,
rewritten/dropped events, changed source/PID, failed journal write, failed purge,
foreign state, partial purge after sidecar loss and acquisition/clock limits. All nine pass; the existing 21
native reception-source cases also pass. These checks validate Python protocol/
ownership logic only, not the C++ bridge, real mixer delivery or a physical peer.

# Native Chat reception source v1

This default-off OVERTE_E2E_FEATURE_TESTS primitive is a narrow prerequisite for
[common Chat v7](../feature_journeys/CHAT_SOURCE.md). It does not implement the
normal Chat UI, source-code association, independent peer actor or full journey.
C++ is source-reviewed only, uncompiled and unexecuted on every device.

## Actual source

MessagesClient connects a test-only direct observer to its original
messageReceived signal when --testScript is present. Original network reception
and original local-only fallback are distinguished by that real signal argument.
No send method, script intent, fixture ACK or requested delivery outcome can add
an event. Product packet decoding/send/subscription behavior is unchanged.

The mutex-protected bounded cache can receive direct signals from script or
network threads. It retains only channel `chat`, the ordinary five-field
send_chat_message JSON shape and exact run-scoped text from the closed fixture
Unicode/reply/hidden/retry inventory. It exports no raw packet, display name,
position, real user text, device selector or session UUID. Records preserve
original capture epoch, reception order, sender digest, channel, text and
localOnly. Legacy forApp compatibility messages are not duplicated in this tap.
A raw native receive does not prove the Chat script accepted/rendered it; Local
distance and actual QML/storage sources require independent joins.

An explicit owned observe opens a run before input; unmatched/late signals do
not create scopes. A run holds at most 128 original events; eventSequence and
actual droppedEvents reveal every discarded original. Whole-history consumers
refuse any drop. At most 32 live runs and 4096 retired-run fences are retained;
fences are never evicted/reused. Native cache/clock/counter failure is unavailable.
A native birth instance and monotonic capture counter span the MessagesClient
lifetime. Epoch regressions permanently disable the source until process restart.

## Closed request and original response

`feature-chat-observe` accepts exactly schemaVersion:1, commandId, action,
operation and runId. commandId is a fresh lowercase 128-bit hex nonce, prefixed
with ios- on iOS. runId is an unprefixed 128-bit hex nonce. operation is only
observe, inspect or retire. There is no text, expected value, sender selection,
message injection, native send/subscription, preferred identity or UI mutation.

Test.featureChatObservation requires the dedicated test flag, --testScript,
actual initialized native lifecycle and owned private results directory. It
queries MessagesClient on its actual QObject owner. The source reads current
native NodeList session identity and actual MessagesMixer node presence/UUID;
no active node is normalized to mixerPresent:false and empty mixerSha256.
No native session identity makes the source unavailable, including cleanup.
This deliberately keeps unresolved intent rather than adopting another context.

The original closed response has chatVersion:1, commandId, runId, operation,
instance, sequence, processId, capturedEpochMs and source. source contains
scopePresent, retired, selfSha256, mixerPresent, mixerSha256, openedEpochMs,
eventSequence, droppedEvents and events. Each event has exactly sequence,
capturedEpochMs, senderSha256, localOnly, channel and text. Digests are
SHA256(ASCII(runId) + ':' + RFC4122 UUID bytes); a display name is never identity.
A real present scope has its original positive opening epoch and contiguous
retained event suffix. An absent/retired scope has zero opening/event/drop
counters and no records. Retired is mutually exclusive with scopePresent.

The existing probe dispatch preserves these original fields in the fixed private
feature-chat-observation.json via the existing atomic 0600 Test writer. It
consumes duplicate command IDs, validates exact metadata and writes unavailable
if the native hook is missing. It does not manufacture empty receive history.
The existing fixture endpoint accepts only the closed iOS metadata variant.
Neither public command nor requested account/peer result becomes a measurement.

## Reader, role association and retirement

The typed reader pins run, native instance, PID, strictly advancing query counter,
original native epoch, local identity and immutable overlapping receive history.
It has a five-second monotonic acquisition budget/51 reads, sends exactly once
and retries only actual private-file reads. It rejects old/foreign/malformed
responses, backwards clocks, changed process/source, rewritten records, future
events and implicit scope resurrection. iOS keeps native epochs separate from
host UTC; the existing bound AFC/PID transfer must enforce the acquisition window.

received_texts requires independently bound actual sender and receiver identity
digests, not display names. The source self digest must match the actual receiver.
Remote reads reject the source's own sender identity and filter localOnly=true;
order and multiplicity are retained, never de-duplicated. This prevents client
self/network echoes from being labeled remote peer delivery. To populate common
peerMessages, acquire this source on the separately bound actual peer process,
with the actual tested client as sender, and independently reacquire it for the
actor witness. The present client-only source/factory is not that peer binding.

ChatCaptureOwner persists versioned private ownership in the existing state
store before native creation. It binds verified candidate/process/session/
fingerprint, run, native instance and native session digest. iOS explicitly
uses NATIVE_UI_COMPONENT_ONLY and remains barred from canonical IPA acceptance.
A fresh scope requires separately observed native absence and durable admission
before observe. A pre-existing scope is not adopted or purged. A failed journal
write permits no native mutation. Lost activation replies retain the admitted
intent for cleanup; no product input is replayed.

Retire first checks actual ownership/source continuity, then removes that run's
cache and installs a permanent native late-reception fence. An ACK is insufficient:
two separately requested fresh inspect responses must show retired, zero actual
records/counters and no scope before the durable journal is discarded. The total
retirement budget is five seconds. Ignored cleanup, lost identity/context,
source replacement, pending private transport or failed final inventory keeps
intent and fails. A never-admitted owner may discard only after actual absence;
it cannot retire a foreign scope. Platform-wide cleanup must attempt this before
normal source/process teardown and must still reach original teardown on failure.

The current 21 host cases exercise original Python/probe/fixture dispatch and
real private local journals against a synthetic native cache. They reject local
and same-receiver echoes, foreign identities/runs, ignored input, missing results,
rewritten/dropped history, false cleanup ACK, failed durable intent/activation,
source/context replacement, incomplete final inventory and clock failures.
They verify observer/owner logic only. No C++/Qt/network/device qualification or
complete feature capability is implied.

The [independent receiver v1](INDEPENDENT_CHAT_RECEIVER.md) now pairs separately
acquired original primary/peer sources and derives an actual remote receive
ledger with durable source/mixer ownership. The existing native read method is
script-invokable on its owner thread in explicitly enabled E2E Assignment Client
processes. This opens a native source seam; authenticated/private actor transport,
send/mixer ownership, complete UI/storage joins and device qualification remain
missing. The default domain peer's heartbeat still proves no Chat receipt.

Version 2 additionally carries the [original DomainHandler session](CHAT_DOMAIN_SESSION.md)
and actual mixer socket activity in the existing source. Legacy v1 packets stay
readable but cannot provide this actual domain/connection-birth evidence. Both
independent v2 source roles pin their original domain lifetime across a mixer-only
outage; no new observation or requested-domain channel is introduced.

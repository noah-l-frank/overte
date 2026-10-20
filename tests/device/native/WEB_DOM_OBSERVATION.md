# Passive browser DOM source v1

`web_dom_observation.js` is an E2E-only common source factory. It is implemented
and host-tested, but not yet packaged/injected by a native backend. It creates
no native view, document completion, bridge grant, input, native acceptance or
complete feature capability. The full browser contract remains
[version 11](../feature_journeys/WEB_SOURCE.md).

## Native integration contract

Install exactly one factory instance at native document start in the actual
main-frame document. Native code must retain its actual view birth, native
frame/origin, grant/page epoch and original inline carrier independently of
JavaScript. The source requires the actual top-level window and browser crypto;
there is no fallback to a host counter or requested document identifier.
Native read commands contain only the exact new 32-hex nonce (optional `ios-`
prefix), never expected text, events, counts, status or source identity.
Call the factory's frozen `read(nonce)` interface through a closed E2E command;
never expose arbitrary JavaScript evaluation as a feature operation.

A result has the closed fields:

- `webDOMVersion:1,requestId,instance,sequence,capturedEpochMs`: an original
  per-document random instance, actual read cursor/time and correlation nonce.
- `document:{runId,href,responseId,readyState}`: actual current location,
  original DOM metadata and browser readiness. The fixture adds one actual
  `overte-fixture-owner` meta element to HTTP and inline input bytes; original
  HTTP response ID remains independently random and server-receipted.
- `editor:{text,focused}`: the actual original `#text` input and active element.
- `attempts`: immutable `{ordinal,capturedEpochMs,eventTimeMs}` entries from
  actual trusted capture-phase click events targeting the enabled original
  `#bridge` button. Read polling, handler assignment, synthetic untrusted events
  and other controls cannot append an attempt.
- `echoes`: immutable `{sequence,surface,message,receivedEpochMs,observedEpochMs}`
  entries requiring BOTH an original incoming parity-protocol signal and the
  unchanged reference handler's actual matching result in `#bridgeStatus`.
  A request/send acknowledgment, copied DOM status, mismatched sequence or
  passive listener without the original receiver cannot populate this history.
  Duplicate original document/sequence receives count once.

The DOM owner label is data, not authorization. The backend must independently
match it to the leased run and actual controlled main-frame URL/source. Join
actual consumed response ID to the unchanged original server receipt. Do not
trust requested resource names, a host fetch, arbitrary meta elements or a DOM
sample alone as native consumption. Inline documents additionally require the
actual immutable native carrier and exact original input-byte association.

`sequence` counts source acquisitions, never completed documents. There are
intentionally no `documentLoads`, `httpStatus`, native/script accepted-message
counts or bridge verdicts in this source. The backend must record real native
completion callbacks once per actual document identity, actual HTTP response
facts/server join, native admission and original script delivery independently.
The independent witness must acquire its own source and must not receive a
primary normalized sample.

## Limits, lifecycle and cleanup

One document retains at most 64 trusted attempts, 64 echoes, 64 pending signals
and four actual bridge subscriptions. Exhaustion permanently blocks reads;
no ring overwrite can turn incomplete history into success. Original text and
status are limited to 512 UTF-16 code units; messages to 4096, actual URL to
131072, sequences to safe integers. Nonregressing original wall time is required;
post-transfer native clock correlation remains the backend's job. The source
attaches only passive listeners plus a 50-ms acquisition timer. It never calls
a page handler, edits DOM text, emits a bridge request or requests authority.

A new actual native document needs a new factory/context and random instance.
The backend retains immutable retired histories across document reconstruction;
it must not substitute a new empty page history for cumulative run history.
Original frame/grant admission must reject a callback from a retired context.
The actual native one-packet inline hold/delivery boundary remains separate
work; this DOM source does not fabricate a delayed callback.

`retire()` disables reads/callback effects, removes its own timer/click listener
and disconnects only its own bridge listener. Thrown cleanup retains unresolved
subscriptions for retry; repeated cleanup cannot silently convert a disconnect
failure into success. A successful JavaScript cleanup call is still not proof
of actual native document/view/inline/file retirement. Native cleanup must
separately observe original resource absence and preserve unresolved ownership.

## Host evidence and remaining adapter work

Nine Node cases run this exact source with the unchanged pinned original
`reference.js`. DOM/OS boundaries and trusted-positive events are explicitly
synthetic; no actual browser trusted event, native bridge or product ran.
Counterexamples cover untrusted/wrong-target clicks, missing bridge, outgoing
only, copied result, missing original receive, unmatched/duplicate echo, owner/
nonce/source/clock faults, overflow, new document identity and failed cleanup.
The twelve original loopback browser resource tests also pass with owner
metadata and independent original response bytes/hashes.

Next: package/inject this source under default-off E2E instrumentation in
Android Phone first, then Pico and iOS; bind real native completion/status/
frame/inline/script facts, normal input geometry, cumulative history, independent
publisher and observed native cleanup. Full capabilities remain absent until
all those pieces exist and their counterexamples pass. Native compilation and
physical-device qualification remain unperformed.

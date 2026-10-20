# Original Phone scene-load lifetime source v1

This passive E2E source observes the actual Android Phone serverless scene
request path and its queued native handoffs. It changes no URL, entity,
navigation decision, request cancellation or product timeout. It does not prove
scene content, a viewpoint, UI success or rendered pixels. Native code is
uncompiled and all physical clients remain untested. No Pico/iOS productive
adapter is implemented by this packet.

## Native observations and lifetime boundary

Under `OVERTE_E2E_FEATURE_TESTS` and the Phone build, Application owns a private
`PhoneSceneLoads` journal. Recording requires `--testScript`. Each actual
serverless request records its real `_serverlessDomainRequestGeneration`, native
UUID, actual resource URL hash, original start/update/release clocks, phase,
pending reference group, actual ResourceRequest result and original byte count.
Only the `location` viewpoint query is removed from the resource hash; this
does not replace the actual URL with a desired scene. Unobserved result/byte
values remain null, not assumed successful zeroes.

A shared native lease is captured by the original ResourceRequest finished
connection and by both actual DomainHandler/application queued handoffs. It
retires only when the last captured reference is destroyed, including actual
QObject connection destruction and execution/discard of queued functors.
`committed` is recorded at the existing final application commit call site;
it does not imply that the corresponding lease has drained. Off-owner-thread
load delivery has its own `delivery` group through the original queued call.
Destroyed requests/functors without a terminal event are explicitly `destroyed`.
Failed/stale/empty paths are recorded without changing their existing behavior.

`pendingLeases` counts retained groups, not individual closures. Zero proves
absence of every traced group, including older requests. It is not an inventory
of every application callback, renderer cache, Web timer or arbitrary resource
request. These observations cover the instrumented Phone scene-load path only.
Independent logical entity, UI, image and fixture cleanup remain mandatory.

At most 128 records are retained per native instance, with no truncation or reset
API. Quota/recording failure irreversibly marks the inventory incomplete; it does
not change the product navigation. An incomplete source cannot satisfy the
required adapter reader. Old metadata cannot hide unobserved new groups.

## Closed command and response

`Test.featureSceneLoadObservation(command)` accepts exactly `schemaVersion:1`,
fresh lowercase 32-hex `commandId`, `action:"feature-scene-load-observe"` and
32-hex `runId`. Run identifies the observer envelope; it supplies no target
generation, URL, expected phase, pending count or result. The getter requires
the original live Test/lifecycle/private-results context and marshals to its GUI
owner. Non-Phone/missing hooks are unavailable.

The existing probe preserves the original native object and writes only
`feature-scene-load.json` through the existing atomic private metadata writer.
It deduplicates the command; it cannot turn periodic replay into new native facts.
The result has exactly `sceneLoadVersion:1`, `commandId`, `runId`, native journal
`instance`, advancing observation `sequence`, actual `processId`, original
`capturedEpochMs`, actual `currentGeneration`, `pendingLeases`, `complete` and
`requests`. Each request row has exactly `id`, `kind:"request"|"delivery"`,
`generation` (zero only for delivery), `resourceSha256`, `startedEpochMs`,
`updatedEpochMs`, nullable `releasedEpochMs`, `phase`, boolean `pending`, nullable
actual `result` and `bytes`. Resource results use the existing native enum 0–8;
phases distinguish requested/reply/parsed/queued/committed/failure and delivery.

## Reader, assertions and failures

`NativePhoneSceneLoads.read(run)` uses the original bound private transport,
actual device clock and existing installed-candidate/process/session guards.
It sends the observation once, polls original-file reads at most 51 times within
five seconds, caps input at 262144 bytes and requires 1500 ms original freshness
including final clock-query/guard latency. Partial writes may retry reads only.
Clock rollback, stale/foreign nonce/PID/context/cursor, duplicate or truncated
history, changed immutable record identity/result, revived released groups,
inconsistent counts/types and incomplete inventory fail closed.

The reader retains original identity/sequence/epoch/history across reads; the
whole owner must durably restore that history across process invocations. Mutable
phases may advance while a group is live. A released row is immutable. Terminal
phase/result and original lifetime timestamps cannot be changed after acceptance.

`committed(original,actual_native_scene_url)` requires a complete source, zero
traced live groups, exactly the current native generation, its actual committed
released request, and a matching resource hash computed from the actual native
address. A commit ACK, newer committed row with an older live group, empty file,
failed/destroyed request or a metadata row for another resource cannot qualify.
This returns the original native row only. The complete Graphics owner still
needs actual fixture delivery, all seven independently observed UUIDs, actual
avatar/camera placement, original rendered pixels and verified restoration.

The internal `_scene_load_observer(...,read_only=True)` factory uses an existing
bound SDK session without repair. Its read-only grammar admits this exact getter
and rejects scene input/expected results. No full feature capability is enabled.

## Host verification

Fourteen shared and three Phone wrapper cases exercise explicit synthetic native
lifetimes and the actual JavaScript dispatch/guarded Phone factory. Counterexamples
cover held commit references, old groups, queued owner delivery, wrong generation/
resource, missing/incomplete source, mutated/revived histories, stale identity/
clock, ignored delivery, partial files and final guard latency. These qualify
the host test logic only; native RAII execution, compilation and devices remain
unverified under the authorized no-build/no-device scope.

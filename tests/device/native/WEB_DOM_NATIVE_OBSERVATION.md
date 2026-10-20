# Native browser/DOM acquisition v1

This common protocol connects the existing `catalog -> OverteSession -> adapter
operation -> native automation` architecture. Shared probe/fixture parsing,
strict Python reader and a default-off Test-to-native-provider bridge are
implemented. Native backend providers are still missing; the C++ bridge is
uncompiled. No complete browser feature capability is advertised.

The exact private command is
`{schemaVersion:1,commandId,action:"feature-web-dom-observe",runId,surface,fixtureUrl}`.
IDs are 32 lowercase hex characters, with an optional `ios-` command prefix only
on the iOS transport. Surface is `world|tablet`. The fixture URL is the original
controlled HTTP(S) run URL ending in `/feature-fixture/v1/runs/<runId>/`, at most
512 characters, with no credentials/query/fragment/control characters. It is a
view selector and ownership input, never a measured result or expected state.
No script text, requested content, expected counters/status, filename or arbitrary
DOM selector is accepted.

The original `Test.featureWebDOMObservation` requires the existing dedicated
build option, explicit test script, writable results location and available
native lifecycle source. It dispatches only the fixed typed native provider
stored under `_overteE2EOriginalWebDOMProviderV1`, on the GUI thread. It creates
no provider/fallback or native view. A backend must register that exact original
callback, select exactly one actual owned native view by surface and original
fixture source, and retain original native request ownership before any async
JavaScript acquisition. An absent/ambiguous/failed source returns unavailable.

The probe writes only `feature-web-dom-observation.json`. It repeats the same
read-only native query while the provider is pending, preserving the original
request. Native providers must return the identical original ready packet for a
repeated completed nonce, without retiming it. Missing hooks write an explicit
unavailable result. Android reuses its original private command channel; iOS
uses the existing private HTTP/AFC channel. Fixture parsing is closed too.

## Original native result

The closed envelope is
`webNativeVersion:1,commandId,runId,surface,instance,sequence,processId,capturedEpochMs,status,source`.
Instance is an original native source birth, sequence its actual acquisition
cursor, process ID its actual OS process and capture time its original native
clock. `pending|unavailable` require an empty source; they are never success.
Ready requires exactly `source:{nativeView,dom}`.

Native view fields are actual
`handle,creation,grant,page,url,nativeFinished,httpErrorStatus,inlineLease,sourceUrl,sourceIdentity`:

- Handle is the actual nonreused native item handle; creation, grant and page
  are original positive native epochs. These values are not command counters.
- URL is the actual current native main-frame URL, equal to the actual DOM
  location in the same guarded acquisition. Source URL and source identity are
  the original native source/session properties, never copied from the selector.
- `nativeFinished:true` requires the actual completion callback for that exact
  native view/creation/grant/page/document. `loading:false` or an evaluate ACK
  alone is insufficient. Duplicate callbacks must not become document loads.
- `httpErrorStatus` is **0 for unknown/no error callback**, or original 400..599
  from the actual main-frame HTTP error response. Zero never means measured
  HTTP 200. The consumed original DOM response ID must separately join the
  original server receipt for full HTTP status/byte qualification.
- `inlineLease` is an actual native carrier observation. Native source **v1 is
  HTTP only and rejects ready inline sources**. An inline DOM owner label cannot
  establish native carrier ownership; a future typed carrier/input-byte lease
  join must qualify that path before its version is enabled.

The original HTTP source must be exactly the controlled run's
`tickets/<32hex>/index.html` or `reference.html` on the selected original origin.
The current document may navigate to B/recovery/the second origin, while the
original native source remains the selected source. Native admission still
uses actual current frame/origin/grant; this source does not grant a bridge.

The DOM field is the exact [passive source v1](WEB_DOM_OBSERVATION.md). The reader
requires its matching nonce/run, actual ready document and fresh source time;
native and DOM times retain the existing -250..1500 ms window against a fresh
independent platform-native clock. Historical attempt/echo times stay original.
Echo history requires an exact original parity packet, matching sequence/surface
and original receive/observation order. No normalized journey outcome is returned.

## Reader and lifecycle

`NativeWebDOMObservation` sends once and polls at most five seconds/51 reads.
All process/installed-code/session guards surround acquisition. Missing,
malformed, oversized, stale or foreign files, missing fields, pending exhaustion,
unknown callbacks, time regression and native unavailable status fail closed.
A repeated pending frame must be identical if its sequence did not advance.

A reader pins one actual native view/document and its native/DOM instances,
original URL/source/epochs, increasing cursors, nonregressing times and immutable
history prefixes. Actual navigation/reconstruction must be explicitly joined by
the full native lifecycle owner before a new reader is created; unexpected
replacement cannot silently reset history. Cumulative document/run histories,
accepted script events, independent publisher, normal input, one-packet inline
hold/retirement and actual native cleanup remain separate required work.

Nine host cases exercise the original reader, original probe JavaScript and
original fixture grammar using synthetic native/DOM/OS boundaries. They include
ignored input, pending progression, changed context/counters/documents, copied
ACKs, missing consumption, native error-status confusion, stale clocks,
truncated history, malformed echo, arbitrary input and absent hooks. They prove
logic only, not native execution, browser behavior or device acceptance.

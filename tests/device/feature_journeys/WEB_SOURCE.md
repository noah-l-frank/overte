# Browser source contract v11 and adapter handoff

World/tablet browser journeys now have 19/26 source-correct shared checkpoints.
The old v9/v10 404-error/reload stub, unobserved foreign stimulus, HTTP-inline
substitution and assumed form retention are rejected. Test logic is present;
complete adapters are missing; native sources are uncompiled and devices untested.
Existing real video/pixel/PCM foundations remain mandatory separate modules.

## Original measurements

All fifteen browser state fields belong to the independently acquired witness:
`surface,text,page,bridgeMessages,bridgeEchoes,attemptedMessages,documentLoads,httpStatus,
origin,documentKind,inlineLeases,deferredMessages,error,focused,open`.

`page` is `none` with no actual document, or the qualified actual original
reference/B/foreign/recovery/inline document. `origin` is independently qualified
`none|primary|foreign|inline`, not inferred from a requested resource. Bind actual
native main-frame URL, view identity, document epoch/nonce, original loaded bytes,
native grant/carrier and PID/start/installed-code source. Public aliases expose
no URL, private identity or selector. `text` is actual controlled original DOM
editor content; focus is the actual editor, not the containing view. Buttons do
not explicitly prescribe native focus: their ordinary aftermath may remain or
release focus, and must be independently measured. Never invoke a DOM handler
or use JavaScript `.click()` as a normal pointer input.

`documentLoads` counts actual completed owned native documents, once per actual
document identity, across view reconstruction in the same guarded process. It
is not a poll/command/ACK/server-GET counter. Native duplicate callbacks cannot
create a second completion. Backend-internal nonce recovery may complete extra
documents, so the contract uses a bounded count plus explicit transition rules:
every Open/navigation/Back/Reload/resume/inline-enter/inline-return must advance;
all other steps retain it. Primary and independently acquired observer samples
must agree on the actual count, including during bounded stable observation.
A fabricated primary increment plus an old secondary document fails.

`httpStatus` is the actual current product main-frame response (200 or 404),
never a host GET or fixture ready flag. `error` remains `none` for ordinary
showable 404 documents on both reviewed native backends. Inline/absent sources
have status 0 because they have no HTTP response. The actual response header and
original DOM metadata must bind to the original response ID/byte hash in the
[owned server inventory](BROWSER_RESOURCES.md). The adapter must acquire that opaque ID from the actual current native
main-frame document, then join the unchanged ID to the independently read
original server response receipt. Native response callbacks/timing status may
corroborate the join; a status inferred only from requested resource names is
forbidden. A header/body ID from a host download alone is not proof of native
consumption. Preserve both source observations and their original timestamps.

`attemptedMessages` is cumulative actual normal fixture Send attempts, across
owned document lifetimes; `bridgeMessages` counts actual accepted original
native/script echo requests. `bridgeEchoes` separately counts actual matching
original page receives, once per original document/sequence, retained as an owned
immutable history across document changes. An outgoing script reply alone does
not populate it. They must be independently observed from actual
trusted DOM input/native dispatch and actual native-to-original-script delivery,
respectively. No request, expected count, native ACK or cooperative DOM echo can
populate either history. Pin original event order, bytes, frame/origin, nonce,
grant/carrier and times; retain immutable bounded event records. `client.js`
deliberately has no origin filter, so native policy must reject a foreign page.
An absent bridge is legitimate there but never excuses a missing normal attempt.
The existing reference DOM accepts only a real matching script echo; a full
adapter must independently inspect that current source too, not just its outgoing
request. Never forward a primary normalized sample to the independent publisher.

## Ordinary browser and server inputs

Open the existing owned parity app/page. Type controlled Unicode through normal
native editor input, then use its real Send button and inspect independent echo
and original native/script receipt. Clear the original editor before navigating:
neither native backend promises form retention through document destruction or
nonce-recovery Back reload. Visit actual B, Back, then the real second origin.
Click its actual Send, observe a real attempted input and zero new acceptance
for three stable seconds, then return to the original origin normally.

Visit `recovery.html`: inspect the actual 404 body/status and native success.
Normal Reload before restoration must complete another actual 404 document.
Activating `restore-resource` uses the reader-owned fixture server control, as
with existing account-provider stimuli. The adapter does not receive the reader
token, issue another restore or mutate the native document; its action delivers
no product input. Inspect the still-current original 404 and unchanged native
document count for three seconds. Only the subsequent ordinary Reload may
produce a new actual 200 document. A requested-only restore fails that checkpoint.
An uncertain fixture activation must be inspected, never replayed.

Navigate to the original reference source URL before background/resume. Both
reviewed backends destroy the underlying view on lifecycle loss; iOS rebuilds
from its original source URL, while Android can preserve a URL archive. Require
a new actual blank reference document and native lifecycle advancement. Type
new controlled reply text and prove real bridge use again. This is usable
resumption, not an invented form-state persistence guarantee.

## Actual inline source and retired message

`inline_source(run,ticket,fixtureUrl)` creates checked original reference DOM and
embedded original `reference.js` with a data-encoded current PNG challenge.
`inline_data_url` serializes those exact UTF-8 input bytes. Neither function
loads a product view or creates a document receipt. Native `InlineHtmlDocument`
accepts this base64 data URL form. HTTP `inline.html` is absent.

`open-inline-app` uses a normal owned fixture-app button calling the existing
public `Tablet.gotoWebScreen(data:...)` route. Its input resource name is exactly
`parity-inline-v1`; it is not a fetched HTTP page. The later adapter must stage
the input in the owned original parity app and inspect actual decoded bytes,
`NativeInlineHtmlSource`, native QML context/root and current document token.
`inlineLeases` is the actual owned active native carrier count (0/1), never a
requested-open flag. Initial open alone requires the inline image challenge;
later inline text/bridge steps use original sources, not relabeled stale pixels.

Prove ordinary inline typing and a real script echo. Then
`hold-inline-message` arms one E2E-only interception and clicks the real Send
button. Retain one original callback **before native admission**, with its
unchanged actual bytes, native document/frame/nonce/token and original times;
do not construct a replay from expected/requested text. Record an actual attempt
and `deferredMessages:1`, with no accepted request yet. Cap the private hold at
one packet/4096 bytes/30 seconds; timeout or missing source fails, never silently
becomes a successful empty result. Native instrumentation stays default-off.

`return-from-inline` uses the ordinary original parity app control to return to
reference. Require a new HTTP document, original inline lease retirement and
the still-retained original callback. `deliver-retired-inline-message` delivers
that unchanged callback through its original native admission boundary exactly
once. Observe the actual held buffer gone, zero active old carrier and no new
native/script acceptance for three seconds. A late old-frame acceptance fails.
This is E2E fault scheduling, never a property setter or fabricated bridge grant.

## Cleanup and limits

The ordinary Close destroys the actual owned page/input/carrier; public page,
origin and document kind become `none`, text/focus empty and HTTP status 0.
Original per-run native event/load counters remain inspectable until cleanup.
Double cleanup must release actual held callbacks, owned app buttons/scripts,
original page/media/bridge/input and private capture/control files; reset/retire
only owned event caches and restore the independently measured original state.
Require three seconds of fresh independent baseline/empty resource inventories.
The known parity script tracks only its ordinary HTTP page, so stopping it alone
must not be mistaken for closing a still-current inline page. Close/verify the
actual page/carrier before releasing script ownership. Unowned resources refuse
destructive cleanup. Original inode/process/source guards remain mandatory.

The existing engine retains 20-second per-checkpoint and bounded sample budgets,
three fresh stable samples, actual lifecycle counters, original image/PCM bytes,
capability gates, private journal roles and no-green missing capability behavior.
The [passive DOM component](../native/WEB_DOM_OBSERVATION.md) now exists with
nine original-reference host counterexamples, but is not natively injected.
The native document/status/callback sources, DOM integration, normal app/button inputs,
publisher and complete cleanup still need implementation Phone → Pico → iOS.
Canonical iOS physical installed-code binding is implemented in its isolated
iOS branch; runtime activation/deadlines and device qualification remain open.
Legacy simulator binding still refuses physical identity.

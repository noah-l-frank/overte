# Original Pico lookup error and durable normal dismissal

This is a component of the unfinished Worlds/navigation adapter. Native sources
remain uncompiled; no device or actual Qt/VR execution is qualified. The full
feature capability remains absent and three of fourteen areas are complete at
source/host level.

## Actual source and cross-thread association

Pico includes the original shared Application setup, which moves AddressManager
to the NodeList thread. AccountManager and its QNetworkReply live on the GUI
thread. A GUI-thread-only callback collector would therefore be unavailable.
`FeatureNavigationReplyCapture.h` passively observes each original scoped reply's
finished signal on that reply's actual owner thread, before the unchanged
original finished callback connection. It reads the actual typed RequestTicket,
final owned hidden-name URL, HTTP status, network error and unpredictable server
response header. A bounded mutex-protected weak registry supplies immutable
facts to the original guarded AddressManager error callback without reading a
foreign QObject's properties or making a blocking GUI call. Normal canceled
requests are discarded through existing scope guards; unrelated URLs are not
exported. The registry bounds live reply identities at 256.

The Pico native reply producer is v2: each immutable event additionally carries
`replyCaptureId` and `replyCapturedEpochMs`, separately from original NodeList
callback time. Other producers remain v1. Shared readers accept both; a live
reader cannot switch versions. The error owner requires v2, a unique capture ID,
ordered capture/callback/modal clocks and original capture after the parent
input barrier. No expected status or lookup generation is sent to native code.

Only `OVERTE_E2E_FEATURE_TESTS && ANDROID_APP_PICO_INTERFACE` adds a diagnostic
QVariantMap argument to the existing not-found signal and matching existing
AddressBarDialog slot. The same original emission point and AutoConnection
queue carry the already recorded event to the GUI. Later lookups cannot replace
its association. The slot unconditionally calls the same original asyncCritical
with the same original title/text and then passively records its actual returned
listener and dialog. There is no extra emission, private-handler invocation,
replacement dialog, response setter or product behavior fix.

`NavigationFailureModals.h` requires the actual TabletMessageBox component and
original MessageDialogButton context, original listener/root weak identities,
actual message/title/critical icon/OK button, current original tablet tree and
actual input geometry. Native `navigationModalVersion:1` exposes immutable
birth/event fields and independently changing root/listener existence, visible
state, actual response result/time and original current UI frame. A modal read
never calls getTablet/getTabletWindow, which can create product UI. The existing
NavigationUi feeds its actual root/window/generation/input/clock frame; a frame
older than 1500 ms or incomplete original tree makes the read unavailable.

The new command is exactly `{schemaVersion:1,commandId,action,runId}`, with action
`feature-navigation-modals` and lowercase 32-hex IDs. Existing lifecycle,
--testScript, private results root, PID/candidate/start and foreground guards
remain mandatory. The original probe writes only `feature-navigation-modals.json`.
There are at most 128 retained modal records and 4096 unique read nonces per
source; the Python reader sends once and polls at most 51 times in five seconds.
It pins original birth/cursor/clocks and up to 32 interleaved run histories.
Dead QObjects cannot resurrect and completed response records cannot change.

## Normal input and durable ownership

`native-navigation-error-controls` v1 adds the optional versioned control to the
existing NavigationUi/PicoNavigation path. The exact original modal/button/token
and reference snapshot are required. Normal ray/pointer input uses the existing
hit-test and pointer callback; no clicked signal or QML handler is invoked by
the adapter. The original QML Android action already avoids a second onClicked
call. A consumed input counter establishes delivery only.

`navigation-error-dismissal` v2 (reading closed v1 journals) is instantiated by the private Pico factory.
The parent must own the failed normal Go To input, selected fixture origin and
source/input lock. It supplies the current dismissal action ticket, original
lookup ticket and original lookup input epoch barrier,
provider identity/configuration and actual same-candidate binding. The owner
joins the separately acquired original completed HTTP write receipt, original
v2 native callback and the one actual current visible modal. A server 404 alone
cannot pass. Wrong origin/ticket/response ID/generation, retired scope or an old
capture is rejected before input.

A private bounded durable journal preserves original packets, joined callback
and receipt, exact pending normal input, original source cursors and unique read
queries. Intent is saved before one OK click. An applied lost reply is resolved
through fresh actual response and weak-object destruction after recreation;
no input is resent and no replacement ticket can adopt pending ownership.
The original HTTP response remains under `lookupTicket`; the current active
provider belongs to `ticket`, the new dismissal action. The owner never
reactivates the old fixture challenge or retags a response. Omitted
`lookup_ticket` retains the older same-ticket call shape. Closed v1 journals
normalize to that same-ticket history and retain their original CAS disk value
until the first ordinary write; unexpected v1 fields and version aliases fail.
A pending input cannot be adopted by a different current or lookup ticket.

Both root and listener must be gone and the original selected button must be OK.
A three-second quiet window then requires unchanged original modal history,
unchanged UI generation/input count, current parent lookup/provider ownership
and advancing native epoch, UI epoch and UI elapsed clocks. Gaps above 1500 ms,
retained objects, stalled clocks or another input/lookup cannot finish.
Even a completed owner requires a fresh current provider/lookup-scope join
before reporting success again. A later active challenge, retired lookup or
advanced lookup generation cannot borrow old completed retirement. The final
action clock is rechecked after persistence.
Each operation has a twenty-second ceiling; at most 81 retirement samples,
eight quiet samples and 512 durable read query IDs are admitted. Historical
originals are validated at their original timestamps without retiming. The
journal remains for the unfinished whole-area finalizer; this owner does not
claim world arrival, unchanged B, restart transfer or complete cleanup.

## Host checks and remaining integration

The explicit eight-module selection covers positive ordinary dismissal,
recreation/lost reply, ignored input, independently retained root/listener,
provider/native/modal source faults, original clock/cursor replay, forbidden
version aliases, capture reuse/barriers, changed geometry, quiet interruption
and changed durable originals. The real owned loopback case keeps the original
404 receipt while activating a different current dismissal challenge. Tests exercise the actual private Pico factories
and existing input router, original probe/Android dispatch and original QML
button functions under Node. A short-lived owned loopback fixture proves the
actual HTTP response header and completed write receipt; native/Qt/device
boundaries remain synthetic. No host pass qualifies C++ thread affinity or VR.

The V8 source review also corrects command admission in the earlier bookmark
source: actual QVariantMap demarshalling converts JavaScript numbers to doubles.
Exact QJsonValue numeric comparison admits the original schema number 1 and
continues rejecting boolean/string aliases. No bookmark wire version changes.

Next compose selected-origin/account/federation/maturity preservation, actual
directory consumption/model and native arrival/stereo, original restart and
bookmark ownership transfer, independent publisher and full resource retirement.
The source/host component never enables a complete Navigation capability.

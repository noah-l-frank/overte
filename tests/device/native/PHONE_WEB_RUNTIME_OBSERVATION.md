# Original Phone Web runtime inventories v1

The default-off E2E Phone runtime source joins actual Qt native-view state and an
independent Android UI-thread inventory/fence. Graphics needs this source because
an absent Web entity does not establish that its browser/document authority has
retired. The source does not implement a full Graphics or browser adapter. C++
and Java are uncompiled and all physical clients remain untested.

## Closed command and original transport

`Test.featurePhoneWebRuntimeObservation` accepts exactly
`{schemaVersion:1,commandId,action:"feature-phone-web-runtime-observe",runId,fixtureUrl}`.
Nonce and run are canonical 32-character lowercase hex. The credential-free
HTTP(S) fixture URL is exactly `/feature-fixture/v1/runs/<runId>/`. There is no
desired count, cleanup flag, JavaScript, arbitrary path or DOM selector. The
getter requires the dedicated build option, explicit test script/results path,
native lifecycle and registered typed Phone provider. Missing/ambiguous data
returns unavailable; it never supplies a successful empty fallback.

The existing private probe writes only `feature-phone-web-runtime.json`, through
the existing private atomic observation whitelist. The internal Phone
`_web_runtime_observer(...,read_only=True)` factory requires the already bound
candidate, existing SDK session and original PID/start identity. Explicit
non-read-only admission is refused. It cannot repair/create a session or send
functional product input. The guarded read-only grammar admits only this closed
observation command.

## Native and Android originals

`phoneWebRuntimeVersion:1` has original command/run, native provider birth,
advancing source sequence, actual process ID/capture epoch, status
`pending|ready|unavailable`, and source `{nativeBefore,java,nativeAfter}` when ready.
The native snapshots bracket an actual executed Android-main-thread inventory.
This is a UI queue fence for preceding ordinary commands, not an acknowledgment
that their browser/document effects succeeded. Those actual effects remain in
the independent inventory fields.

Each native snapshot has original epoch, `complete`, append-only `knownHandles`
and current `views`. Nonreused original handles have immutable first-observed
epochs and actual first-owned source SHA. That time is explicitly first observed,
not an invented native creation timestamp. Views include actual creation/grant/
page, source/document/creation URL hashes and scope membership, session active/
authorized state, created/pending/retry/suspended/loading facts, scoped original
registered JS callback membership, current script reply count and actual pending
E2E DOM acquisition. Callback origin metadata is recorded without retaining a
QJSValue or changing delivery/removal. Quota failure marks observation incomplete.
Only original active callback-map membership qualifies a pending callback.

The Java packet has its own process birth/sequence, actual process/epoch,
completeness, current WebViews and original pending `CREATING` entries. Current
views expose actual creation/grant/page, active/destroyed/closing/host/foreground/
loading state and independently read requested/current-document source hashes
and membership. Pending creations preserve their actual original source argument
alongside the existing owner/revision. The snapshot executes on the Android UI
thread and runs no JavaScript, activation, navigation or destruction. It is gated
by the existing native E2E enablement; normal product decisions are unchanged.

Unrelated source URLs are not exported. Only owned fixture URL hashes and
previously observed owned handles are retained; a neutral cached native shell
can therefore remain visible in the inventory after its owned document retires.
This source does not claim global browser-process, network, JavaScript-engine or
all-Qt-callback enumeration. Revoked-grant callbacks are governed by existing
product generation checks; they are not relabeled as measured queue absence.
Complete feature cleanup must additionally prove actual entity absence, native
scene-load drainage, provider retirement and a stable independent quiet window.

## Time, continuity and verification

The provider has one pending observation, a four-second native completion budget
and an immutable cached completed response per nonce. Repeating that nonce
preserves its actual epoch and packet. The reader sends once, polls at most five
seconds/51 reads and rejects missing, malformed, oversized or explicit unavailable
results. Pending timestamps remain request history and are never refreshed as
current facts. A ready packet requires every original native/UI clock ordered
within 1,500 ms, fresh final independent time and unchanged installed/process/
session guards. A separate local elapsed-age floor prevents a frozen native clock
from hiding a slow UI fence. No current header can borrow a pre-request snapshot.

Native and Java births/cursors/clocks are independently pinned. Original handle
history must retain its exact prefix; duplicate/foreign rows, incomplete scans,
wrong process or nonce, regressing counters/clocks and missing fields fail.
Source bounds are 128 native views, 128 Java views, 128 pending Java creations,
256 observed handles per run, 32 retained runs, 1,024 scoped callback origins per
native item and 262,144 bytes per private packet. Exhaustion is unavailable,
not truncated success. No process restart resets a reader implicitly; the full
area owner must explicitly archive and prove each role's old/new process boundary.

`active_marker(packet,source_url)` is a separate assertion using a freshly
independently observed entity source URL. It requires exactly one current world
native view and the same actual Java handle, creation, grant/page and document
hash with live own source authority. It returns original rows only. It cannot
prove world-target pixels; the independent original GPU/image evidence remains
mandatory. `released(packet)` separately requires observed prior ownership,
both native snapshots without owned source/document authority, pending creation/
retry/scoped callbacks/replies/DOM acquisition, and no owned Java document or
pending creation. Original known source hashes also prevent false membership
flags from hiding retained source authority. Neutral cached shells are allowed;
owned documents and retained pending resources are not.

Nineteen shared host cases use explicit synthetic native/Java originals and the
actual JavaScript probe. They reject live Java remnants despite entity absence,
pending creation/callbacks, falsely cleared membership, never-observed emptiness,
missing/incomplete/foreign results, rewritten handle history, stale/pre-request/
reversed/frozen clocks, changed births/cursors, mismatched document grants and
unsafe commands. Three actual Phone wrapper cases verify existing-session
admission, no SDK repair, original release/live-state checks and closed grammar.
They establish reader/probe logic only. Native/Java compilation and physical
lifetime behavior remain explicitly unqualified.

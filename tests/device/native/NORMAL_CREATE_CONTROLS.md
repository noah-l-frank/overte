# Native Create controls v1

`NormalCreateControls.h` identifies existing `NativeCreate.qml` elements and
reads their original values on the GUI thread in an explicitly enabled
`OVERTE_E2E_FEATURE_TESTS` / `--testScript` run. It changes no product behavior.
`NormalControlUi::Surface::Create` / `CreateUi` supplies the Phone transport;
Pico and iOS may reuse the same identities and metadata in their existing
normal-input bridges. Native source is uncompiled and unqualified here.

## Original source and reference

The Create page must be the actual QML `root` in a local file/qrc context ending
in `/system/create/qml/NativeCreate.qml`, with typed tab/error/status properties
and its real `sendToScript(QVariant)` signal. Component URL SHA-256 is a
location fingerprint, **not** installed-code identity. A separately verified
candidate/process/session/source profile remains mandatory. The page, current
selection, original field contents, combo index/count and geometry participate
in native control-token invalidation. No requested state is used as evidence.

`token_create_ui.snapshot` accepts exactly `createControlsVersion:1`, `open`,
`ready`, `scope`, `controls`. `open` must be an independent native tablet state;
`ready` is the actual current bridge readiness. A closed tablet has no controls.
Scope contains actual native `instance`, `generation`, consumed-input
`sequence`, monotonic `elapsedMs` and `processId`. Instance and control tokens
are nonzero lowercase 32-hex/canonical UUIDs; native integer generations are
also accepted. Reads must not create input sequences. Per-reader instance/PID
are pinned and native clock/input counters cannot regress.

Every regular row contains `id`, original `token`, `enabled`, `focused` and
`inputReady`. The page adds `profile:native-create-v1`, `tab` (0..4), unique
nonzero canonical `selectedIds` (at most 256), `statusError`, bounded actual
`statusText`, and `componentSourceSha256`. Page input is prohibited. Malformed
or incomplete page/selection data is unavailable, never a default empty result.
Fields add their actual printable-ASCII `text` (at most 4096 characters).
Combo rows add actual `currentIndex` and `count` (host 2, shape 6); entity rows
add original canonical `entityId`. Scrollbar rows add original normalized
`position` and `size`. No unknown keys, duplicate IDs/tokens or false types are
accepted. Controls are limited to 384; native traversal to 4096 items/128 levels.
Navigation rows permit the existing `tablet.home` / `tablet.page.1..32` shape.

## Input and ownership

The recipe uses a mandatory owner callback **before every input**, carrying
only `{createInputVersion:1,action,controlId,controlToken,scope}`. It carries no
field text or fixture results. The caller must persist this intent in its
private process/session journal and refuse unrelated existing panels/entities.
Pass the complete captured reference to `activate`, `replace`, `select_index`
or `scroll`. Immediately before dispatch the backend must call
`same_reference(original,current,id)` (or perform equivalent strict native
admission): identical instance/generation/PID/input sequence/row, native elapsed
age 0..5000 ms. Never replace the original reference with a new selection/token.
Persisted outer ownership is still required after uncertain delivery; an input
ACK is neither an entity observation nor permission to discard cleanup intent.

Normal input means a pointer event at the actual resolved visible item, focused
field IME/key input, focused ComboBox Home/Down/Return, or a scrollbar trough
pointer event at geometry derived from its actual thumb. The select-index path
requires the original combo or its own visible popup content to own focus.
No `setProperty`, QML handler invocation, Create bridge message or Entity API is
an input route. Replace/activate/scroll also require actual hit ownership;
a modal/overlay must not be clicked through. Unknown actions/IDs are refused.
Native intent consumes its command sequence before uncertain event dispatch.
The host requires a fresh consumed-input counter after dispatch, and separately
waits for actual focus/text/index/tab/selection/scroll-position transitions.

Transitions have ten-second waits with bounded 100-ms polling. Entry discovery
uses the actual available tablet pages and at most seven reads per page.
Reveal scans actual scrollbar positions in both directions, at most 32 steps
each and a ten-second deadline checked before each step (an outstanding single
transition may use its own ten-second budget). Missing/covered/off-screen
controls and unchanged scroll positions fail; no guessed coordinates or hidden
field input is allowed. All observations and journals are private artifacts.

## Composition and remaining work

`TokenCreateUI` implements the same UI interface consumed by `NormalCreate`:
open/wait, avatar Cube, original UUID selection, name/properties/Apply,
Undo/Redo, delete, owned JSON import. The existing read-only observer must
measure actual entity host/owner/properties, import parenting and history.
Selected IDs and displayed text alone cannot prove these effects. Creation
intent records the pre-input actual ID set before Shape; uncertain input is
never replayed. Original UUID ownership, late-result observation and unresolved
import cleanup remain governed by `NormalCreate` and its private state.

Host tests compose that owner and the existing synthetic native observer with
a separate synthetic widget boundary. They detect consumed-but-ignored input,
widget/entity disagreement, stale/foreign references, clock/PID regression,
failed intent, failed reveal, partial creation, incomplete deletion and
unresolved import. They exercise Python control logic only; C++/Qt and all
physical devices remain untested. This packet does not implement model/texture,
JSON file picker/export, PolyVox, permission actors or the full
`feature.create.*` v8 coordinator, and advertises no such capability.

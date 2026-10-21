# Original Phone Emote widgets and ordinary input, version 1

This E2E-only component reads the actual original PhoneEmote.qml and sends normal
Qt window input through the existing `NormalControlUi` owner. It neither changes
Emote functions nor reports Rig/pose effects. Native C++ is uncompiled and all
physical clients remain untested. Full Phone Emotes is still incomplete.

## Original controls

`Test.phoneEmoteUi` is available only in the existing Phone feature-test build
and active `--testScript` scope. Original GUI-thread traversal retains the normal
4096-node/128-depth/384-control upper bounds. The Python Emote contract is more
restrictive at 64 controls. The original QML context/root, local file/qrc component
source, actual ten-name model, typed active label, status property and signal
shape identify the widget family. The component URL hash identifies its actual
source location; it is not a content hash or runtime Script execution proof.
Actual executed Script code and installed resource roots need separate originals.

| Control | Original metadata / input |
| --- | --- |
| `emote.page` | Read-only profile `phone-native-chooser-v1`, actual active label, actual ordered ten-name model, original component URL SHA256 |
| `emote.grid` | Actual contentY/originY/contentHeight/viewportHeight/moving/dragging; ordinary window wheel input up/down |
| `emote.play.<name>` | Actual name, original model index and highlighted state; normal pointer click |
| `emote.entry` | Actual EMOTE tablet button; normal pointer click |
| `tablet.home`, `tablet.page.1..32` | Existing actual tablet navigation controls; normal pointer click |

Allowed names are Crying, Surprised, Dancing, Cheering, Waving, Fall, Pointing,
Clapping, Sit and Love. There are no direct Sit1/2/3 inputs, overrideAnimation or
restoreAnimation commands. The actual chooser randomizes Sit; its native Rig
history must independently reveal the selected variant. Cancel uses a normal
second click on the actual active button. An empty label supplies no Rig proof.

Every raw observation has exactly schemaVersion/commandId/action, original
instance/generation/sourceSequence/lastCommandSequence/elapsedMs/capturedEpochMs/
processId, `emoteControlsVersion:1`, actual ready and controls. Each control has
original ID/token/enabled/focused/inputReady plus only the row metadata above.
Tokens change when original objects, active labels, grid position, geometry,
readiness or source context change. Inputs preserve the caller's original token
through another host acquisition and native re-resolution. The native sequence
is consumed before dispatch; lost/ignored input is never replayed.

Normal pointer events enter the rendered window with actual clipping/hit-test.
Scroll uses a `QWheelEvent` inside the actual visible GridView, with no contentY
assignment, QML handler invocation or guessed scroll effect. This is a native
wheel input recipe, not a claim to have tested Phone touch swipes. The reader
measures actual scrolling and waits for motion to settle. Virtualized/offscreen
buttons must be reached through real grid progress, not synthesized metadata.

## Python recipe and private transport

`TokenEmoteUI(io,intent)` owns only input delivery. Its mandatory intent callback
must durably retain the complete original widget snapshot and exact pending
control/action/sequence/instance/generation before any input. The caller owns the
existing input session, held source lock, tablet UI leases, original Script/code/
resource association, feature run and any pending input recovery. It must refuse
a lost or changed scope instead of recreating a successful empty state.

`open`, `play(name)`, `cancel` and `close` use actual current controls. The recipe
retains source cursor/birth/clock continuity, waits at most ten seconds per UI
transition, allows at most twelve actual scroll inputs and enforces a twenty-
second whole nested operation limit. Missing controls, ignored scroll, motion,
changed tokens, wrong highlight/model metadata and changed contexts fail. A
consumed Play input may still have no functional effect; no animation/pose state
is returned. Complete native Rig history and original rendered pixels remain
mandatory before a feature checkpoint can pass.

`PhoneEmoteIO` uses the existing private command file with outer action
`phone-emote-ui` and original result `phone-emote-ui.json`. Observe contains only
schemaVersion 1, 32hex commandId and action. Input additionally contains the
original instance/generation, next sequence, observedElapsedMs, controlId/token
and action `activate|scroll`; only scroll adds direction `up|down`. Extra fields,
wrong types/nonces, control characters and direct variant/setter requests fail.
The actual probe deduplicates commands and records available:false for a missing
native hook. Its ACK is only a consumed ordinary input, never an effect verdict.

The candidate-bound `_emote_controls(selector,intent,read_only=False)` factory
preserves actual APK/process/session/generation and target checks. It reads actual
SDK tablet visibility separately. `read_only=True` requires an existing session,
never repairs it and permits only exact native Observe requests; input fails
before transport dispatch. The capture limit is the existing five seconds/51
reads; successful final freshness is at most 1.5 seconds, including actual SDK
lookup time and a separate monotonic elapsed-age floor. Original raw native
packets remain available as `original_packet` for a future durable measurement
owner; that owner must save accepted originals before another acquisition.

## Cleanup and qualification boundary

The caller closes only its owned chooser/tablet, independently verifies actual
Rig restoration, releases any world/controller inputs, confirms no timers or
owned callbacks and restores the original scene/camera/UI before retiring its
host journals. This input component provides none of those success verdicts and
advertises no `feature.emotes.*` operation. Missing full capability fails the
existing mandatory area gate.

Ten shared widget counterexamples and ten actual Phone IO/factory/probe cases
use synthetic product/SDK boundaries, explicit independent widget state and the
actual JavaScript command grammar. They include ignored play/scroll, lost input
receipts, changed tokens/candidates, private read-only admission, frozen clocks,
missing sources, refused direct variants and absent full capability. The combined
251-test Phone wrapper regression passes. These are test/input logic checks;
native compilation, actual layout/wheel/touch behavior, Rig/pixels/actor evidence
and physical qualification remain open.

The final shared no-build selection passes 1,187 tests with zero failures,
errors, skips or attempted compiler launches. Exactly three compiler-based
native voice checks were explicitly excluded. Documentation, contract-registry
validation and actual probe JavaScript syntax checks also pass.

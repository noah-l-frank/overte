# Phone immediate Graphics component

`_graphics_controls(selector, intent)` binds the shared ordinary-input recipe to
the original Phone Qt/private probe channel. The required owner callback must
persist validated input/preference ownership before every input. No complete
`feature.graphics.*` capability is advertised; full render/actor/restart and
original preference cleanup coordination remain mandatory.

The closed outer command is `{schemaVersion:1,commandId:<32hex>,
action:"phone-graphics-ui",request:<inner>}`, with identical IDs. Observe is
schema/ID/action only. Inputs use the existing native instance/generation,
next command cursor, original observed elapsed time and control ID/token.
`activate` is restricted to the ordinary entry/toggle controls; `scroll` adds
only direction up/down; `set-value` adds only a finite normal slider target.
The original probe rejects extra fields, booleans/nonnumeric values and unknown
controls/actions. Missing `Test.phoneGraphicsUi` publishes `available:false`.

The default-off feature-enabled native Test hook reads actual original Render
resolution/haze/mirror settings on the GUI owner and uses the same
`NormalControlUi` core as the existing Script/Audio inputs. It does not read or
write an expected result. Ordinary Qt pointer events enter the original window,
with actual track/scrollbar geometry and original scene hit-test. No Render
setter, QML handler/signal or synthetic UI state is exposed as an input route.

Original results are private `phone-graphics-ui.json`. PhoneGraphicsIO validates
exact source fields, real process ID, new request/capture barrier, native source
cursor, instance/root/window generations and actual token/metadata under the
existing installed-APK bytes, PID:start, foreground and target/session guards.
Read-only retries are bounded to five seconds/51 reads. It compares the supplied
original token through its additional fresh capture and native re-resolution;
a new layout/value token is never silently substituted. Uncertain input is
never replayed. Later readback must show original Qt and native agreement.

Offscreen controls retain read-only above/below metadata; input remains
unavailable until measured scrolling exposes them. Missing/outside controls
cannot trigger guessed scrolling. Original preferences must be recorded before
any modification and remain reachable on the actual slider grid. An ACK or a
changed preference cannot fill the complete journey's renderScale/hazePass/
mirrorPass/image fields. See [the shared contract](../../native/NORMAL_GRAPHICS_CONTROLS.md).

Seven new wrapper/probe counterexample cases bring the Phone focused group to
52 passing cases. They include normal original restoration, ignored/UI-only
slider input, retired tokens, missing replies/source and installed-candidate
replacement. They exercise actual Python/probe dispatch with explicit native
widget boundaries, not an APK, renderer or device. Native C++ is uncompiled.

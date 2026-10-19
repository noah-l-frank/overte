# Normal Audio controls, version 1

This is an internal input component, not a complete `feature.audio` capability.
Native C++ is source-only and uncompiled; the host boundary tests validate the
recipe, not Qt delivery, native audio, acoustics or device acceptance.

`NormalAudioControls.h` identifies the original Audio page and existing controls
by actual QML type/properties. The platform owner must supply an atomic original
AudioClient-thread voice observation plus actual mute, local-echo and current
HMD mode. No input accepts those measured values. Missing history-version/cycle
source makes the component unready. `audio.page` is an observation marker,
never an input target or a native overlay button covering the page.

`NormalControlUi.h` retains the existing Script-file core, now shared by the
`ScriptFileUi` and `AudioUi` surfaces. Existing file wire version stays 1.
Audio wire version is `audioControlsVersion:1`; root/process/window generations,
actual QObject plus source-key control tokens, native monotonic command cursor,
5-second observed-input lease and consume-before-delivery behavior apply.
Every Audio row includes actual `enabled`, and a separate `inputReady` flag.
The latter requires original audio/Qt coherence, the actual current audio mode,
and no pending recording request. Only the current Desktop/VR profile can be
selected. Inactive echo and mute readbacks must agree with original AudioClient.

Audio metadata fields are closed by `token_audio_ui.metadata_fields` and checked
by `validate_metadata`. The page contains `mode`, `nativeHmd`, `uiHmd`, `cycle`.
Record contains native cycle/active plus actual Qt `uiActive`, `requested`,
`phase`, `label`. Echo contains cycle/active/request plus actual Qt/native echo.
Mute contains actual checked/native mute and selected mode. Mode rows contain
actual checked/native context. Scrollbar contains actual finite position/size.
Tokens retire when cycle, active context, mode, checked/echo or scroll geometry
changes. Ongoing PCM counter changes do not churn an active Cancel token.

Input is a normal Qt pointer press/release or existing original native/VR
control route. Never emit `clicked`, invoke QML handlers, assign checked/mode/
position, call AudioClient Start/Cancel setters, or synthesize successful state.
For scrolling, use the actual scrollbar thumb and groove geometry, not wheel
input over gain sliders. Re-resolve the original token immediately before
input. The shared Qt core also rejects a point covered by a foreign visual item.
The only Audio actions in that core are `activate` and `scroll` (`direction`
exactly `up`/`down`). The page and scrollbar cannot be activated as buttons.

`TokenAudioUI` pins instance/generation and native HMD context and rejects native
cycle regression. `io.capture` must independently establish request, process,
clock and fresh source cursor at the existing platform boundary. `io.activate`
and `io.scroll` must compare the supplied original token against the current
resolved item and preserve it through delivery. They must never substitute a
newer token. The owner callback must validate and persist the intended operation
before each input. A failed callback prevents input. ACKs only mean delivery.

Normal actions are bounded to 10 seconds/101 observations, with at most seven
actual scrollbar advances; every advance requires measured position change.
Start requires one actual cycle increment; it returns the actual UI observation,
which can be a muted-microphone error, and proves no capture/playback success.
Cancel requires the owned active cycle, sends once, then requires that same
cycle's actual cancelled phase and inactive native/Qt state for 300ms. Natural
completion cannot satisfy cancellation. Inactive Cancel is refused because that
same product button would Start another recording. Mute/echo toggles require
independent original readback; ignored input is never replayed.

Missing replies, stale tokens, restart, native-context change, ignored input,
ambiguous widgets, a blocked groove or unknown phase fail closed and preserve
the owner's unresolved intent. The owning adapter must keep durable panel/cycle
ownership, stop only its recording/echo, restore measured initial mute/mode and
panels, release original PCM through the separate evidence source, and verify
cleanup independently. An initial idle/history-empty Audio contract requires a
verified real process restart, not an instrumentation reset. This primitive
does not implement that coordinator or acoustic evidence and does not advertise
any full-area capability. The canonical iOS installed-code association block
continues to apply to all private source/input components.

# Phone normal Audio component

`_audio_controls(selector, intent)` returns the shared token/cycle guarded input
recipe using `PhoneAudioIO`. The required owner callback commits validated input
intent before every ordinary input. This internal component advertises no full
`feature.audio.*` capability and does not own the page/session automatically.

The existing candidate/APK byte, PID:start, process/session/generation and target
fingerprint guards run before/after private-channel reads. Requests use closed
`{schemaVersion:1, commandId:<32hex>, action:"phone-audio-ui", request:<inner>}`.
Inner command ID must match. `observe` has exactly schema/ID/action; input has
instance/generation, next command sequence, observed native elapsed time,
control ID/token and action. `scroll` additionally has direction `up`/`down`.
No state, expected values, setters or direct Audio methods are accepted.

The original probe calls feature-build-only `Test.phoneAudioUi`. An unavailable
hook saves `available:false`. Original results are written privately as
`phone-audio-ui.json`; Python validates exact fields, actual process ID, native
instance/generation, advancing source cursor, fresh timestamp/request barrier,
and 5-second/51-read bounds. Partial asynchronous JSON is retried read-only.
Input preserves the recipe's original token through an additional fresh capture
and native re-resolution; it never adopts a replacement token. Native input
intent is consumed before dispatch. Missing/foreign ACK cannot replay input.

Native AudioUi reads actual voice history/cycle, mute and echo on AudioClient's
thread and actual current HMD context on the GUI owner. It uses the same
`NormalControlUi` owner as the existing file picker. Ordinary Qt pointer events
enter the real window. Scroll input uses the real scrollbar groove on the
requested side of its actual thumb, with actual scene hit-test; it never changes
volume sliders, assigns QML properties or calls Start/Cancel directly.

The shared [version 1 contract](../../native/NORMAL_AUDIO_CONTROLS.md) defines
state coherence, cycle retirement, bounded waiting and cleanup responsibilities.
The full durable Audio page/recording/echo ownership coordinator, original
acoustic fixture and verified restart cleanup remain open. Native C++ remains
uncompiled and device behavior unqualified. Host Phone tests exercise the real
candidate-bound Python wrapper and original probe JavaScript against explicit
independent Qt/transport fixtures; they do not execute an APK.

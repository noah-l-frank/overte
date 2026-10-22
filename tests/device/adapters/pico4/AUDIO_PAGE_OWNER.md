# Normal Pico Audio page owner

`PicoAudioPageOwner` / `run_normal_audio_page()` execute a bounded, private
vertical segment of the existing Audio recipe. The normal path is:

1. Preserve original native Audio settings, peak state, empty preview taps and
   actual closed-tablet/VRKeyboard baseline.
2. Open the tablet through the existing process-bound OpenXR adapter session;
   independently observe real Home and original stream neutralization.
3. Activate the normal Audio entry using its original token. Bind the actual
   canonical Audio.qml page/context/root/window identities and original peak
   restoration property. Original control-cursor advancement proves delivery,
   while the independent page/settings/Lifecycle channels prove effects.
4. Claim the existing `AudioPreview` owner, normally mute, and issue one normal
   recorded-preview Start. Require the actual new native cycle and original
   `error/microphone-muted` terminal event with zero captured/played/total bytes.
   The cycle's actual start timestamp must follow the saved original pre-input
   source fence. An old event cannot borrow the new ordinary Start.
5. Restore original mute through normal controls, preserve other original Audio
   and mixer settings, and reuse the existing owner for native quiet and actual
   memory/file tap release. A release acknowledgement alone is insufficient.
6. Press the ordinary Pico X through the existing session, independently prove
   actual Audio page destruction, Home return and original input peak restore.
   Preserve the separately retained QQmlContext instead of calling it dead.
7. Prove three seconds of original Home/native/PCM quiet, press ordinary X to
   close the owned tablet, then prove another fresh three-second quiet window.

The full original UI/settings/Lifecycle packets and post-release PCM-absence
packets remain in the private, bounded compressed journal with SHA-256. Both
quiet windows retain their exact original frame indices. All nine original
native/host clocks must cover three seconds; a gap over 500 ms resets a window.
Historical windows never replace a fresh read after reconstruction. A repeated
closed-boundary invocation acquires a new final window without sending input.

The owner, all three readers and existing preview component share the exact
parent ScriptJourney source-lock instance. Normal token input and all three
original controller envelopes/neutral proofs remain separately journaled.
Every first possible input follows durable intent and final source freshness.
Final result construction/persistence and the last guards are included in both
native age checks and independent host monotonic lower bounds.

Cold recovery reconciles original effects and cursors without sending an
uncertain entry, mute, record, restore or X again. A lost native release response
uses only actual absence inspection. A claim-only gap can acquire new read-only
sources and create its private preview journal because claiming sends no normal
input. An intent gap before the preview component has any original pending or
committed action remains unresolved. It is not permission to infer consumption
or resend. Unknown/changed owners, missing originals, retired candidates and
unobserved effects fail with journals retained. Base cleanup also refuses an
orphan page-owner journal, including when no preview owner was ever created.

The `audio-page-owner` Pico group executes the real owner, existing preview,
readers and original session/factory code with explicit independent audio, UI
and controller host boundaries. It covers the complete segment, original true
and false peak/mute states, lost entry/mute/release responses, acknowledgements
without actual page/tablet effects, hidden retained pages, failed peak restore,
old native events, changed original contexts, final clock/copy aging and fresh
quiet after reconstruction/gaps. Native observer and unchanged full Audio.qml
checks remain in `audio-settings-source`; neither group is device evidence.

This is not complete `feature.audio.*` qualification. The remaining recipe needs
actual unmuted physical stimulus, independent acoustic output and peer channels,
capture/cancel/completion/interrupted/background joins, and all original
external actor/recorder/publisher resources and process-owned QObject/timer/sink
scopes closed with actual original evidence. Accepted native sink-write PCM is
not acoustic capture. The page context, native observer objects, all journals
and source originals remain owned. No complete Audio capability is advertised.

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=<private-directory> \
python3 android/vr/pico/tests/pico4-test-suite.py \
  --test audio-page-owner --test audio-preview-owner --test coverage-matrix
```

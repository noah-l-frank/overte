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
8. With actual settings version 2, wait read-only for original native callback
   capture destruction and an exact match of the observed original resource
   baseline. Then require another three seconds of independent original quiet
   while that resource match remains true. Passing the original 30-second delay,
   PCM absence or a dead receiver cannot substitute for native retirement.

The full original UI/settings/Lifecycle packets and post-release PCM-absence
packets remain in the private, bounded compressed journal with SHA-256. Both
quiet windows retain their exact original frame indices. All nine original
native/host clocks must cover three seconds; a gap over 500 ms resets a window.
The final native wait is bounded to 40 seconds and retains every original
sample. No new normal input or source callback is registered while waiting.
Its completed quiet windows are derived from the same saved original frame
indices, including every native lifetime DTO; the journal format is unchanged.
The report separately exposes actual callback retirement, observed resource
baseline match, and native lifetime quiet windows. A retained capacity or newly
created stopped polling timer prevents a resource match even with empty PCM.
Historical settings version 1 reports those lifetime facts as unavailable;
`await_deferred()` refuses it instead of treating missing originals as zero.

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
quiet after reconstruction/gaps. Explicit original callback publications are
also composed with the entire normal version 2 flow; frozen pending callbacks
after the requested due time, retained allocation capacity, and resource changes
during the final quiet window fail while retaining journals. Native observer and unchanged full Audio.qml
checks remain in `audio-settings-source`; neither group is device evidence.

[The positive capture continuation](AUDIO_CAPTURE_OWNER.md) can take ownership
after claim or after normal mute restoration, before tap release. Once it has a
journal or original PCM, this muted segment cannot send a competing action or
release its native taps.

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

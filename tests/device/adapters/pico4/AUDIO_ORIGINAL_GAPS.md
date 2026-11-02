# Remaining independent Audio originals and cleanup boundary

The normal dispatcher remains partial. This audit reads the current shared
sources. The original audit pinned Phone revision
`abb7f6b60d97daf17752aadf94e2b5df099bb7ba`. The later
[digital original join](AUDIO_DIGITAL_PREVIEW_JOIN.md) selects a narrow shared
provider/file-reader slice from frozen Phone
`a7be274da152b9d0b77e2fe5bb9874c5b1e18a31`. Neither audit runs audio routes,
peer services or devices. The reused digital monitor does not supply physical
acoustic evidence or a complete independent Audio witness.

## Reusable original components

The existing [voice signal](../../voice_peer/voice_signal.py) implements the closed
`recorded-preview-v1` profile: all twelve challenge symbols fit inside the real
three-second recording, with independent full-capture and quiet-negative checks.
The [fixture](../../feature_journeys/fixtures.py) already derives its stimulus
from the real run and recording-start ticket. The [evidence analyzer](../../feature_journeys/evidence.py)
can analyze original WAV bytes with this profile. These are stimulus/analysis
components, not microphone or loudspeaker acquisition proof. The actual
[Engine evidence code](../../feature_journeys/engine.py), lines 186–187, binds
completed Audio file/acoustic evidence to `recorded_ticket`, the original Start,
rather than the later await-completion ticket.

The existing [voice runtime](../../voice_peer/runtime.py), `AudioRoutes.capture`
(lines 140–166), records a real owned `parec` process and validates its source
stream against the private receive sink. Its actual source is
`self.names["rx"] + ".monitor"`: a digital client-output loopback. It cannot prove
Pico physical microphone capture or loudspeaker acoustic output. The receive
legacy receive path chooses the default `voice-v1` signal/analyzer,
requires that profile's longer capture interval, and replaces
`receive-capture.wav/json` on the next receive. The additive
`receive-preview`/`preview-files`/`preview-release` APIs now preserve the exact
separately owned start-ticket WAV/JSON pair under the existing explicit test
flag, with the closed recorded-preview profile. The same normal Pico recipe
joins its retained cycle3 input/sink originals to these independently decoded
digital bytes and retains full physical signatures and original JSON bytes.
Actual microphone/loudspeaker acquisition, independent worker/process-birth
and complete route/lifetime/Actor publication still need their own originals.
No digital loopback is relabeled acoustic evidence.

The actual existing PC virtual microphone send route is a digital network
stimulus. Neither it, a requested challenge, `Audio.playSound`, native input tap
PCM nor accepted sink PCM establishes physical microphone/loudspeaker behavior.

## Missing operations

A genuine independent acoustic source still needs an owned physical stimulus
and external recording route, actual device/route/process birth, run/Start-ticket/
native-cycle timing binding, arm/read/cancel/release, bounded original bytes and
missing/short/stale-capture errors. No such producer is present in the reviewed
normal Audio adapter sources. It cannot be replaced with a WAV made from the
requested challenge or the local accepted sink tap.

The independent witness also needs its own actual original source consumption
and actor token, with fresh cursors and the shared source-lock instance. The
shared Audio witness requires recording/preview/mute/frame/buffer/phase/history/
error fields. A remote actor cannot infer local native preview history/frame
counts from a network receive ACK. Reusing the primary packet or its expected
projection would not supply independent peer observations. Physical OS permission
recovery remains its separately composed prerequisite.

## Executed whole-cleanup incompatibility

This boundary follows executing code, not only handoff prose:

* [feature_journey.py](../../modules/feature_journey.py), lines 39–51, captures the
  original process identity and asserts it around every actual observation.
  Only `continuity('after', 'restart-app')` explicitly replaces that identity
  (lines 46–49).
* [engine.py](../../feature_journeys/engine.py), lines 80–83, calls continuity
  before and after observations. Cleanup (lines 500–513) activates cleanup,
  invokes it twice, then waits for the restored initial baseline. That path
  performs no `restart-app` continuity transition.
* The actual [Audio scenario](../../feature_journeys/scenarios.py), lines 195–224,
  has an idle/empty-history/zero-frame initial baseline and no restart-app stage.
  The original [AudioClient getter](../../../../libraries/audio-client/src/AudioClient.cpp)
  retains the actual completed native cycles/history. Private tap release does
  not erase those product originals or prove capacity/timer/context release.

Therefore an adapter-hidden process restart would violate the actual original
process assertion; keeping that process preserves real native history rather
than restoring the scenario's empty initial history. Existing Scripts/Auth/
Graphics restart handoffs have explicit identity transitions and do not authorize
an Audio-hidden transition. A future explicitly reviewed common test-architecture
change must resolve this boundary; this packet changes no shared contract,
continuity assertion, cleanup baseline or product behavior. Until then it retains
all original journals/PCM and reports complete qualification false.

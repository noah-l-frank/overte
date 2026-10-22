# Original Pico Audio settings source

`PicoAudioSettings` is a private, read-only component. It does not register a
complete Audio capability. The planned normal page owner needs this source to
prove that opening and closing the original Audio page restores its input peak
setting. The actual `Audio.qml` enables `devices.input.peakValuesEnabled` on
completion and restores `peakValuesWereEnabled` only on destruction.

`feature-audio-settings-observe` accepts only schema version, command ID, action
and run ID. The original `TestScriptingInterface` getter requires the dedicated
feature build, actual test-script runtime, private results directory, foreground
lifecycle binding, HMD mode and already available dependencies. It never creates
a dependency, enumerates a device, reads the potentially initializing
`peakValuesAvailable` getter, or writes a setting.

The getter reads original AudioClient state, scripting Audio properties, input
peak state and NodeList mixer gains on each original owner thread. Avatar/server
injector gain is read directly from the already present NodeList; the scripting
gain getters can acquire that dependency. Five weak object identities are fixed
for the observer's run. Actual replacement or destruction makes subsequent
publication unavailable, without adopting a new object or claiming retirement.
The script, devices and input objects are read together on their actual common
owner thread. Those device/input getters return embedded members of the held
original Audio dependency; no raw child association crosses a queue boundary.
The published role map carries QPointer originals acquired on those actual
threads, so death before publication is unavailable.

Cross-thread reads use four closed, bounded queued channels. Worker reads wait
at most 200 ms; original TSI dispatch waits at most one second. Heap-owned
results outlive a timeout, callbacks capture weak original receivers, and no
callback captures caller stack references or an unheld child. A timed-out
callback is canceled and stays owned until Qt actually destroys its original
functor, including original receiver destruction. Later queries discard its
result and require original queue retirement before fresh publication. Only
the actual currently executing TSI dispatch is excluded from that pending
check. A live blocked worker cannot grow new queued observations or supply a
late fresh value. The host checks cover blocked worker/GUI queues, destruction
before delivery and child destruction between original script/device reads.

Each component has its own timestamp recorded before its first getter. A later
envelope cannot refresh an earlier component value. Version 2 includes the
original AudioClient preview lifetime DTO in the same bounded client-thread
observation. Actual callback registration, entry, completion and final captured
lease destruction, timer identity/liveness/activity, and byte capacities remain
original facts. The strict lifetime reader validates complete cycle membership
and immutable event history. Empty PCM, an elapsed requested delay or a dead
receiver cannot retire a callback.

Historical version 1 remains readable. A live source cannot change between
versions; version 1 has no lifetime evidence and cannot acquire it by migration.
The native receiver identity is retained independently of the existing Audio
role identity. See [the native lifetime source](AUDIO_PREVIEW_NATIVE_LIFETIME.md).

The strict reader preserves original raw bytes and SHA-256, fixes PID, native
instance, run, role identities and monotone cursors, and supports passive
historical restore. Every source timestamp must follow the actual request and
remain at most 1.5 seconds old. Result copying, hashing and the final guard are
included in the final native clock and independent host monotonic lower bound.
It uses the exact existing ScriptJourney source-lock instance. Missing or
malformed publication fails without replaying the query or ordinary input.
Distinct native/script mute snapshots remain separate facts; a caller must
independently establish coherence before using them as a restore boundary.

The `audio-settings-source` Pico group runs the real factory, seven explicit
source/probe boundary cases, and a Qt host compiler check. The compiler check
executes the entire actual Pico getter body and original native observer with
explicit AudioClient/Audio/NodeList seams and real worker threads. Typed Qt
properties, missing dependencies, runtime/HMD/private-path gates, source object
replacement/death and current-command deduplication are covered. It also compiles
and runs the original non-Pico empty getter. This is not an audio engine,
physical microphone, acoustic output or device test. Existing native recorded
preview PCM/history and accepted sink-write bytes remain separate channels;
none establishes an independent acoustic verdict.

Normal Audio open/exit, full recipe composition, independent acoustic and peer
observation, background recovery and complete process/resource retirement remain
outside this component. Owner journals and original evidence are not removed.

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=<private-directory> \
OVERTE_NATIVE_QT_MAJOR=5 OVERTE_QT5_HOST_ROOT=<existing-qt5-root> \
python3 android/vr/pico/tests/pico4-test-suite.py \
  --test audio-settings-source --test coverage-matrix
```

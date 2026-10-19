# Atomic recorded-preview history, version 1

This is a read-only native source extension for the shared version 3 Audio
workflow. It does not start/cancel a preview, supply samples, reset product
status or claim audibility. It requires the default-off feature instrumentation
and explicit test launch. Native C++ remains **uncompiled and device unqualified**.

`AudioClient::startRecordedVoiceTest()` records an E2E cycle counter, original
start epoch and actual capture output format only when normal Start really
reaches the audio thread, including rejected Start attempts. The normal status
publication records each actual event once with its original global event
sequence/time. Every new normal Start begins a new cycle/history. Repeated
reads, PCM release and UI acknowledgments cannot create/reset this history.
At most 64 events are retained; overflow marks the source incomplete and cannot
qualify. These bounded counters/statuses contain no PCM or account/device data.

`featureRecordedVoiceObservation()` copies live native buffer/capture/playback
state, original latest event and cycle history in the same audio-thread call.
This avoids constructing one state out of differently timed reads. Its original
seven fields remain supported by narrow readers. A complete history additionally
has exactly `historyVersion:1`, `cycle`, `startedEpochMs`, `captureSampleRate`,
`captureChannels`, `historyComplete:true`, `events`. The historical format is
kept separately from the current output format. A changed output device after
completion cannot reinterpret the old recording's frame count.

Cycle zero, empty latest event/history, zero native live buffers and zero
historical format/start identify the actual never-started state. Missing hooks
or missing extension fields are not that baseline. An idle state cannot be
recreated by releasing instrumentation PCM after a terminal product status.
A real verified application restart/new source context is needed to restore it.
The metadata intentionally survives private PCM lease expiration/release, just
as the product retains its last status; original PCM evidence still has its
separate bounded lifetime and source/cycle/hash checks.

The shared `NativeFeatureObservation.read(...,require_recorded_history=True)`
requires this extension. It preserves the platform's original candidate,
PID/start/session, native request fence, source clocks and five-second/51-read
bounds. All three isolated platform transports reuse this enclosing reader;
the canonical iOS installed-code gate still refuses it. Once observed, a
history-capable source cannot silently become an older narrow source.

`recorded_preview_history.py` checks typed complete native histories, contiguous
actual event sequences, original times, legal phase transitions and monotonic
byte counters, including progress observed between timer events. A later
terminal event cannot regress behind already observed live capture/playback. The first event is Capturing or an actual Start error. A terminal
event ends that cycle. Completed means Capturing/Playing/Draining/Completed,
equal whole three-second captured/played bytes and empty live product buffers.
Active format and whole-frame counts must agree. A same-cycle read must preserve
the original event prefix and format/start; a new cycle must advance native
cycle and global event sequence. Returned data cannot mutate the reader's copy.

`measured_state(packet)` projects the validated actual native packet into the
version 3 Audio fields, leaving real UI presence to the platform UI owner. File
recording's separate `audio.recording` flag is never used as voice-preview proof.
During capture/play, frames come from actual live counters; after termination,
they come from the original terminal event while `bufferedFrames` remains the
actual empty live buffer. Consecutive repeated phase publications are compressed
for the public history; missing phases are never synthesized. Mute comes from
the native packet. A history/projection alone is insufficient: the full adapter
still needs normal source-token UI inputs, original input PCM, independent
acoustic evidence, permissions in the existing foundation, actor journal and
verified cleanup/restart ownership.

Eleven device-free tests exercise actual parser/projection/history logic using
explicit simulated native boundaries. They cover initial/capture/completion,
missing instrumentation, changed historical events, dropped prefixes, incomplete
history, phase/sequence gaps, retained buffers, changed formats, real new-cycle
semantics and forged idle reset. They do not compile or execute AudioClient.

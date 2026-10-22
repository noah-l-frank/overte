# Normal final Audio X and private PCM closure

`PicoAudioFinalClose` consumes an original retained terminal capture through
`_audio_final_close(target, run, cycle, phase_source, capture=...)`. It reuses
the exact parent, native readers, controller session and source-lock instance.
The original current `close` fixture ticket supplies input metadata. The last
capture and parent manifests stay fixed, and its original input/sink PCM files
are revalidated with their saved file identities before each public operation.
No peer or acoustic result is inferred from those digital taps.

The owner requires the original mute/settings/gains restored and no pending
normal input before releasing private taps. The existing Preview owner checks
three-second terminal quiet, records its private release intent, inspects actual
memory/file absence and checks another quiet period. An uncertain release
response recovers by inspection; an intent gap without its original requested
state remains unresolved. The capture originals and native event history stay
owned and unchanged.

Each normal X uses the existing `PicoOpenXrAdapterSession`, a durable original
envelope, its original pre-input source fence and independently read native
neutralization. The first X must destroy the actual original Audio.qml page,
return to Home and restore its original input-peak setting. A merely hidden or
detached retained page fails. The original QQmlContext may remain alive and is
reported separately. After three seconds of fresh Home quiet, another normal
X must close the tablet. Closed quiet uses all ten original native/host clocks;
gaps over 500 ms reset that window without removing earlier frames.

The same original process, lifecycle counters, terminal native recording event,
cycle, settings, gains, absent editor/VRKeyboard and released private taps must
persist. This directly consumes existing Preview native history after the page
has disappeared; it does not require or fabricate a surviving Audio UI.
Full raw source packets and controller envelopes remain in the bounded private
journal. The fixture's exact active instance, birth and ticket history are
rechecked after the durable X intent immediately before staging outside the
controller lock, and before returning a fresh observation.
Report copies, journal writes and final guards count toward source age.
The controller's locked intent callback performs private host CAS and fsync
only. Its monotonic bound uses the previously captured original fixture/native
anchors and includes all callback work. No HTTP, fixture clock, source guard,
native query or controller session is reentered there. Original PCM files are
rechecked before each final freshness guard as well as at public entry.

A lost acknowledgement after the controller's original cursor commit can read
its native neutral/effect without resending. A lost grant-commit reply before
that host cursor commit remains unresolved even if a page effect is visible.
The owner never adopts an uncertain cursor, repairs a process or repeats X.
Orphan final journals block base cleanup and competing Preview release.

The optional read-only deferred wait requires actual native callback retirement,
then three seconds of fresh quiet with that exact original lifetime/resource
snapshot. Elapsed due time, empty PCM, stopped recording and receiver death do
not retire a callback. Actual retained buffer capacity, polling-timer objects,
Qt contexts, history and journals remain owned. Baseline resource equality is
reported separately; a normally retained allocation can leave it false while
the measured X/peak/private-tap boundary is proven. No implicit restart or
journal retirement occurs, and complete Audio qualification stays false.

`audio-final-close` checks normal input/recovery and the actual private factory.
`audio-final-retirement` separately checks original callback/resource boundaries.
Both use explicit host source seams; unchanged original AudioClient/Qt lifetime
and Audio.qml behavior remain covered by `audio-settings-source`. No physical
microphone, acoustic capture, peer or device execution is claimed here.

# Original Pico Audio page lifetime

`AudioPageObservation` adds a private, read-only `picoAudioPageVersion: 1` /
`picoAudioPages` snapshot to the existing original normal Pico navigation
publisher. Existing shared Audio control metadata and normal input delivery
remain unchanged. The dedicated feature build and real test-script runtime are
required. The source matches the actual `PathUtils::qmlUrl("hifi/audio/Audio.qml")`
and the actual QML context's `root` identity, rather than a matching object name.

Each original page retains separate weak page/context/tablet-root/window IDs,
individual liveness flags and its actual `peakValuesWereEnabled` property.
The first observation timestamp is not called a creation time. Hidden and
detached pages stay retained. Actual page destruction can leave the original
QQmlContext alive; the source reports both facts without deleting Qt internals.
The observer keeps at most 64 page originals and 256 weak object identities and
never adopts a replacement as an existing original. Ambiguous or changed
partial identity makes the source unavailable.

`PicoAudioPages` preserves the entire original navigation packet and SHA-256,
binds PID and original bridge, and serializes under the exact existing
ScriptJourney source-lock instance. It requires advancing original publication
cursors, append-only page history and monotone liveness. Each successful read
includes final copying/hash work and the last guard in the final native-clock
and host monotonic age checks. The optional native fields are validated by the
existing Pico navigation reader. Absence cannot masquerade as a new source.

The original Audio page enables input peak collection during completion and
restores its captured original value during destruction. A host Qt5 test loads
the unchanged complete repository `Audio.qml`, its original styles and controls,
and the weak observer. Only native audio services and tablet sounds are explicit
host seams. Both initially enabled and disabled peak states, real completion,
hidden/detached/reattached pages, name-only impostors and actual page destruction
are covered. The native output is also validated by the Python reader. An
isolated network namespace prevents page assets from initiating external access.
No audio engine, device, microphone or acoustic capture is run.

This component is part of the existing `audio-settings-source` Pico group and
is preparation for normal open/muted-rejection/restore/close ownership. It does
not implement the complete Audio recipe, independent acoustic/peer proof or
process-owned resource retirement. Journals and source originals stay owned.

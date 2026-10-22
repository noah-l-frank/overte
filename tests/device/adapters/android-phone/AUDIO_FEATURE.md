# Phone audio feature composition

The Phone adapter composes the complete common v17 `audio` journey through
`feature.audio.act|observe|cleanup`. Its mandatory catalog foundations remain
`permission.snapshot|set`, `sound.play`, `voice.exchange` and normal `audio.mute`.
The common recorded-preview detector judges original microphone-input and
independently captured PC playout WAV bytes. The native accepted-write sink is
also acquired and checked separately. An input acknowledgement, expected phase,
desired tone, HTTP input description or codec counter alone proves no outcome.

This is source and host composition. The focused native contracts compile
original entry bodies on the prepared Qt 6 host. A complete Android translation
unit, APK, physical microphone/speaker and device run remain unqualified. No
global acceptance count changes.

## Explicit configuration and independent observer

`OVERTE_PHONE_FEATURE_AUDIO=1` enables the complete extension only for an already
candidate-bound controlled debug Phone target with both
`OVERTE_E2E_VOICE_TESTS=1` and `OVERTE_E2E_RECORDED_PREVIEW_TESTS=1`. Missing mandatory
foundation capabilities reject registration. The default is zero.
`OVERTE_PHONE_AUDIO_CONFIGURATION` names a private mode-0600 JSON file:

```json
{"audioConfigurationVersion":1,"artifactRoot":"/private/run-artifacts","peerState":"/private/prepared-pc-state","peerClientSha256":"<independently pinned client SHA-256>","peerRunnerSha256":"<independently pinned runner SHA-256>","domainId":"<original domain UUID>"}
```

The two directories must already satisfy the existing private ownership boundary
and equal `OVERTE_DEVICE_ARTIFACT_DIR` and `OVERTE_E2E_VOICE_PEER_STATE` respectively.
The prepared PC client and isolated Pulse monitor use the existing voice fixture;
the adapter does not launch them. The runner pin hashes the concatenated original
`voice_peer.py`, `runtime.py`, `voice_signal.py` and `peer.js` bytes in that order.
The private PC session itself is independently hashed and remains bound throughout.
The PC preview source additionally requires `OVERTE_E2E_RECORDED_PREVIEW_TESTS=1`.

The controlled fixture explicitly opts into `audioProvider: {"fixtureUrl":
"http://controlled-host:port/feature-fixture/v1"}`. Its adapter credential is
supplied by the existing private `OVERTE_PHONE_FEATURE_FIXTURE_CONFIG`; ordinary
application inputs never receive that credential. `script_observer.py` version 3
accepts area `audio` and reconstructs its own actor, native/UI/HTTP readers and PC
file acquisition. It never calls primary Observe or consumes its projection.
The read-only command gate admits only original status/files observations.

## Normal input and original sources

Normal tokenized Audio page entry, Record, Cancel, Mute and Back inputs are
journaled before delivery. Lost returns are resolved from fresh original native
and UI state and are never automatically replayed. Permission, focus/background
and mute recovery retain the common journey's existing checks. The independent
PC receiver must actually be recording before normal Record begins.

The Phone-only, testScript-only PCM seam can arm only while the existing real
input device and supported original input format are available. It waits for an
actual hardware callback and the original preview capture cycle. It replaces
that callback's input with bounded controlled PCM, retaining all original mute,
stream, resampler, preview, gate, encoder and packet paths. It cannot start
recording, manufacture an input device, unmute or bypass the codec. Its 15-second
lease and actual callback/format/cycle counters fail closed. The previous voice
foundation's source is never concurrently enabled.

The native HTTP reader obtains the exact current ticket's immutable PCM input
through Qt Network, with no redirects, cache reuse or caller-provided samples.
Its original response ID, bytes, SHA and request timing join independently read
server socket-write receipts and phase history. A release aborts pending input
and invalidates old callbacks. Command IDs cannot replay an old release against
a new lease. Input bytes are deterministic fixture material, never observations.

Original AudioClient preview history and independently read private native PCM
files establish microphone and accepted-write sink samples. Actual emitted
non-silent codec bytes are required as an additional source. The separately
running original PC client contributes its actual isolated playout monitor WAV,
client/runner pins, original audio statistics and current domain/routing state.
Each PC files/release query carries a fresh echoed request ID. Metadata, ACKs or
Phone-local sink bytes cannot stand in for PC playout. Physical acoustic hardware
is explicitly not claimed by these digital-path measurements.

## Durable retirement and verification limits

Private versioned owners bind candidate, session, process, source instance,
ticket, phase and separate role histories. Native input, sink and PC WAV records
retain original provenance and their actual private file bytes, device/inode,
size and SHA through planned/opened/saved/deletion states. Missing, changed or
incomplete originals prevent green retirement.

Cleanup cancels through normal UI, restores Mute and local echo, releases owned
input and PC captures, and closes the normal page. The existing preview history
has no normal reset; the audio-only cleanup contract therefore permits exactly
one durable normal stop/launch replacement. A fresh independent process query,
old PID ESRCH, new original native instance and launch counter must agree with
the unchanged candidate/session. The other thirteen common areas retain their
original process binding. Ignored restarts and later PID changes remain red.

Both roles complete their original quiet windows. Every resumed finalization,
including an old retirement plan after partial journal deletion, reacquires
fresh native memory/files/input absence, actual idle/UI state, old-process
absence, PC capture tombstones and controlled fixture retirement. It reopens
actual owned host files before deletion. A second cleanup/finalization is
idempotent. No timeout, private-file or source-freshness bound is increased.

Focused host tests run the complete unchanged common v17 journey over the real
loopback provider with explicitly synthetic UI/native/process/PC producers.
They cover lost input, actual source/codec omissions, candidate/process changes,
mutated or absent originals, late native files after an old retirement plan,
incomplete primary quiet state and partial deletion recovery. Separate tests
exercise the actual PC file-owner methods, original HTTP socket receipts,
default-off registration and all fourteen common module bindings.

The prepared C++ contract compiles the actual `PhoneAudioFixtureInput` and
`PhoneAudioFixtureHTTP` headers and verbatim AudioClient availability/arm/read/
release and `Test.phoneAudioFixture` bodies. Qt supplies actual HTTP, file and
thread transitions; hardware descriptors and unrelated dependencies are fixtures.
It checks non-test launches, actual callback/format/lifecycle gates, command
replay, redirect/oversize/error responses and late callbacks after release.
This focused qualification does not replace a full Android build or device run.

The shared probe changes require the integration owner's final combined Emote
source-pin regeneration. This feature does not regenerate those pins itself.

Verified locally on 2026-10-22: 19 new Phone audio cases (including the complete
common journey), nine HTTP/PC source cases, four all-area cleanup binding cases,
28 existing recorded-preview cases, 258 existing adapter cases, 103 common
journey cases, 16 normal Audio UI cases, 11 fixture credential cases, 15 phase
fixture cases, 21 Graphics resource cases and 13 browser registration cases.
The final read-only late-native-file counterexample and all five Audio feature
cases were rerun after hardening finalization. Three existing original Voice
compiler cases and the new original Audio entry contract also passed. The
repository checks (151), project coverage checks (five), Phone inventory and
probe JavaScript syntax passed. The documentation contract's ten regressions
passed; its global Android class/SDK/count-profile comparison remains pending
the integration owner's combined update. No device or PC audio process ran.

Focused reproducible entry points include:

```sh
python3 -m unittest discover -s android/phone/tests/device -p 'test_audio*.py'
python3 -m unittest discover -s tests/device/self_tests -p 'test_audio*.py'
python3 -m unittest discover -s tests/device/self_tests -p test_feature_module_audio_cleanup.py
python3 android/phone/tests/audio-fixture-source-contract-test.py --build-dir build/audio-source-fresh
```

The native contract requires a new owned build directory, Qt 6 Core/Network
development packages and a C++17 host compiler. The mandatory Phone runner lists
these focused checks; it was not executed as a broad build/device runner.

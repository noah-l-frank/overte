# Original memory-preview evidence, version 1

This is E2E-only instrumentation for the **existing** automatic three-second
Record-and-Play control. It changes no preview timing, gain, normalization,
permission decision, sample, input device, output queue or product setting.
It requires `OVERTE_E2E_FEATURE_TESTS=ON`, explicit `--testScript` and a private
existing `--testResultsLocation` directory. It is not a full audio adapter or
proof of hardware playback. No native build/device qualification has occurred.

## Native sources

`RecordedPreviewObservation` runs solely on AudioClient's owning thread. Each
ordinary `startRecordedVoiceTest()` starts a new monotonically numbered cycle,
including failed starts. It copies the exact newly accepted capture bytes
**before** the product buffer's preview normalization, and the exact successful
`_loopbackOutputDevice->write()` bytes **before** their removal from the pending
queue. A partial device write is copied exactly, without padding. The sink tap
includes real silence delivered during capture, followed by normalized replay.
It does not assume equality between pre-normalized input and sink samples.

The observer records the original native phase events, sequence and timestamps.
It never supplies a signal or calls Start/Cancel. The supported source format
is signed little-endian PCM16, mono/stereo, 8–48 kHz. Unsupported format,
overflow, more than 64 native events or an expired lease makes evidence
unavailable. Capture is bounded to 16 MiB, accepted sink writes to 32 MiB.
An AudioClient timer clears the E2E source after 30 seconds; a new cycle also
clears the previous one. Normal product buffer cleanup remains unchanged.

## Closed acquisition and cleanup commands

All three commands have exactly `schemaVersion:1`, `commandId:<32hex>` (HTTP/AFC:
`ios-<32hex>`) and `action`:

* `feature-recorded-audio-observe`: calls only the native evidence getter. The
  GUI snapshots AudioClient on its owner thread, atomically writes two original
  files and publishes `recorded-preview-observation.json` through the existing
  probe. A duplicate request returns its original cached metadata and timestamp.
* `feature-recorded-audio-release`: clears only E2E observation buffers and
  removes matching owned E2E files. It **does not cancel** a product preview.
  A feature cleanup must first use ordinary Cancel, independently verify that
  playback/buffers stopped, then release observation data. The release response
  is exactly `{schemaVersion:1,requestId,released:boolean}`. The host additionally
  checks actual file absence. Repeat release must succeed without new resources.
* `feature-recorded-audio-files`: independently reads actual native filesystem
  existence and observation-memory state. After release, the host always issues
  this separate read with a fresh request ID. Its envelope has the same native
  identity/sequence/request/capture/PID fields as acquisition, with `files` and
  `memoryEmpty` replacing `source`. `files` contains the two fixed names in the
  table below, each with a typed observed `exists` boolean. Either an existing
  file (including a dangling symlink) or retained memory makes cleanup fail.
  Android additionally verifies absence through run-as. iOS never interprets
  an AFC/WebDriver 500 transport error as proof that a file is absent.

No desired phase, expected audio, PCM samples, test verdict, path or filename
is accepted. Missing hooks publish `available:false`, which is rejected.
The metadata is bounded to 262144 bytes and acquisition, including both binary
transfers, to five seconds. Failed/foreign/partial observations never replay a
product input. A retry may repeat only a new read-only acquisition.

The metadata has exactly `schemaVersion`, `requestId`, `instance`, `sequence`,
`requestedEpochMs`, `capturedEpochMs`, `processId`, `source`. The native instance
is the same dedicated source instance as the normal native feature observer.
`source` contains exactly `cycle`, `startedEpochMs`, `sampleRate`, `channels`,
`inputLastEpochMs`, `sinkLastEpochMs`, `events`, `input`, `sink`.
Each file descriptor has exactly `name`, `tap`, `bytes`, `sha256`:

| Name | Original tap |
| --- | --- |
| `recorded-preview-input.pcm16le` | `capture-before-normalization` |
| `recorded-preview-sink.pcm16le` | `loopback-device-accepted-write` |

The parser retains native times/cycle/event history and requires hashes/lengths
to match separately transferred bytes. Events are bounded, ordered and typed;
completed capture/play counts must equal three seconds in the observed format.
Consumers supply `after_cycle` from a pre-input sample to reject an old completed
recording wrapped in a new acquisition. Source times are native times; iOS uses
the native request fence and the bounded host monotonic interval across clock
skew. No host timestamp is substituted for the capture timestamps.

## Privacy and independent proof

Files are fixed direct names, atomic QSaveFile writes with mode 0600 in an
isolated 0700 directory. Symlinked paths, existing unowned/changed files and
shared permissions fail closed. Native tracked digests prevent overwriting or
deleting another writer's artifact. A GUI lease removes owned exported files
30 seconds after the last successful acquisition. Failed removals remain a
cleanup failure. Runner teardown must inspect retained files and remove only
the owned isolated results directory after evidence collection.

Android transfers use existing run-as/exec-out with a closed fixed script,
regular-file/link-count/mode/size checks and explicit binary completion frames.
Missing files are distinct from failed transport. iOS uses original Documents
AFC bytes and its native process guard; this component does not overcome the
canonical installed-code association blocker.

The host may wrap these unchanged PCM samples in a WAV header for the existing
`recorded-preview-v1` detector. Record challenge identity is generated outside
the adapter and never passed as a desired sample to the native source. The
source and accepted-write PCM establish application audio data, **not** acoustic
output or a physical microphone. A real controlled external source/recording
and independent peer remain required for the complete audio journey.

Device-free tests exercise the actual Python reader, original probe dispatch,
HTTP command validator and Android shell file checks with explicit native
boundaries. They prove test/control logic only; the new C++ is uncompiled.

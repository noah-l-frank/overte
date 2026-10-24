# Partial iOS original PCM snapshot ownership

All twelve focused PCM cases pass in the combined 63-test Stop/floor/PCM run
(17.697 seconds). Actual bounded binary carriers and private journals are
exercised; audio, UIKit, native clocks and transport producers are declared
models. Native compilation, acoustic output and devices remain unqualified.

```bash
PYTHONPATH=.:tests/device:tests/device/self_tests:tests/device/ios/self_tests python3 -m unittest -v -f test_ios_audio_pcm_lease.AudioPCMLeaseTests
```

The local run additionally used the private TMPDIR, no-build verification
overlay, bytecode suppression and unique blocked-attempt log; no blocked
attempt was recorded.

`audio_pcm_runtime.lease` constructs an internal `IOSAudioPCMLease` under the
actual recording owner's lock and installed candidate. It uses the existing
`FeatureObservation.recorded_preview_observer` / `RecordedPreviewEvidence`
iOS Documents transport. The selected normal recording operation, input
ticket, native cycle and original source reference remain unchanged.

Snapshot and release request IDs are durably committed before actual native
delivery. A lost snapshot result cannot invoke another allocation. A lost
release result permits only a new independent native files/memory query; it
cannot invoke another release. A completed original may be decoded again
without making it newly current. Native clocks bracket actual snapshot and
absence acquisition independently of host transfer timestamps. The shared
25-second owner API budget and original 1.5-second acquisition bound remain.
Before allocation, an independent native files query must find both tap paths
absent. The original normal cycle already retains evidence memory before a
snapshot request (`RecordedPreviewObservation::begin`); its actual nonempty
baseline is preserved rather than reported empty. Unknown existing tap files
cannot be overwritten or released by a new lease after metadata loss.

The snapshot retains actual input and sink PCM bytes in 64 KiB chunks using
the common immutable original store. Each carrier remains below its existing
1 MiB limit. Stored bytes must match the native byte counts and SHA-256 values,
owned native event prefix, source birth, cycle and recording format. A digest
or a loopback-device accepted-write tap does not establish acoustic playback.

Release acknowledgement is insufficient. Retirement requires a separately
queried, independently clock-bracketed native original reporting both named
tap files absent and native evidence memory empty. An ignored release remains
owned without resend. Cleanup of an uncertain allocation returns `captured:
false`; it cannot replace an unavailable recording or authorize a whole Audio
pass. Lost metadata, missing originals and incomplete original writes remain
unresolved. Host originals are retained; this packet does not delete them.

The full Audio adapter still needs independent acoustic and Actor evidence,
configuration/public routing, automatic-completion observation, permissions,
mute and background recovery, page restoration, cross-owner input fencing and
whole process/SDK cleanup. This internal packet activates no capability.
Focused host tests use explicit UIKit/audio/native transport models with real
private journals, locks and original carriers. Native compilation and devices
remain untested.

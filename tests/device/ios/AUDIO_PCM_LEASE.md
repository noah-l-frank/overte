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

An existing version-one lease resolves its entire saved recording binding
against exactly one actual owned Start in the current parent history. Later
ordinary starts cannot relabel that original or prevent its pure decoding.
A new lease still selects the latest actual Start. Ticket, native cycle,
original reference and operation digest must all agree; malformed or detached
bindings remain unavailable. An unretired earlier lease cannot release a
newer current cycle: the fresh native cycle check still precedes release.

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

The [current normal page/cycle owner](AUDIO_PAGE_CYCLES.md) now joins ordinary
page/mute restoration and automatic completion to this lease. Full Audio still
needs independent acoustic and Actor evidence, configuration/public routing,
permissions and background recovery, actual page lifetimes, cross-owner input fencing and
whole process/SDK cleanup. This internal packet activates no capability.
Focused host tests use explicit UIKit/audio/native transport models with real
private journals, locks and original carriers. Native compilation and devices
remain untested.

The multi-cycle regression first reproduced the earlier/latest binding error.
The corrected original sixteen-case PCM selection passes in 17.561 seconds.
A connected normal page case passes in 9.770 seconds: automatic completion,
original PCM capture/release, a later capture cancelled by ordinary mute,
unmute, another capture, OS background/activation, original child adoption and
ordinary page return. Pure archive keeps the first lease bytes and inode and
does not query or release again. The declared producer explicitly allocates
new evidence memory for later starts; that memory remains owned. The earlier
absence original is historical and proves no absence for those newer cycles
or whole Audio cleanup. No capability, schema, acquisition window or API
budget changes in this correction.
The final 41-case explicit PCM, completion, background-bridge, legacy and
authorized-page selection passes in 53.803 seconds, including malformed saved
bindings. Earlier failure diagnostics remain retained separately.

The dedicated native PCM observer also uses the repository's Qt-version
boundary: Qt 6 accepts native-endian `QAudioFormat::Int16` only on little-endian
hosts; Qt 5 retains its explicit signed-16/little-endian predicate. This avoids
calling removed Qt 5 format members in the Qt 6 test build. Channel/rate limits,
original bytes and observer gating are unchanged. This source correction was
reviewed against `AudioDeviceCompat.h`; no compiler or native execution was
used, so both native compilation paths remain unverified.

`input_wav()` now provides lossless host RIFF/WAVE framing of the exact original
input PCM, with its observed sample rate and channel order. It reads and
validates the retained snapshot/chunks and adds only a standard container
header in memory. It creates no native WAV/export, allocation, SDK request,
current clock sample or new ownership journal. The original PCM carriers remain
the authoritative files. This internal byte projection does not yet expose a
complete public Audio observer.

Five explicit framing/common-detector cases pass in 6.998 seconds. Original
inverted stereo remains separate; wrong run/ticket/profile, a signal present
only in the digital sink, missing chunks and same-byte inode replacements
cannot qualify. Historical framing performs no queries or writes and preserves
all source bodies/inodes. The connected ordinary authorized-page case now
passes the unchanged shared `recorded-preview-v1` file detector before release
and page close (5.411 seconds). Its audio waveform and native/WDA producers
are declared models. The first connected edit used a nonexistent field on a
compact source reference and failed before PCM delivery; the test now retains
the actual normal Start ticket directly. No native source or evidence clock
was changed to resolve that test error. Digital input detection establishes
neither actual microphone origin nor independent acoustic playback/peer
receipt; those remain required for full Audio admission.

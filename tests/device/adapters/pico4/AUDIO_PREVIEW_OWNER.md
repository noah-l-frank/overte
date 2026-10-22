# Pico normal recorded-preview owner v1

Audio remains **partial**. No `feature.audio.act`, `feature.audio.observe` or
`feature.audio.cleanup` capability is advertised. This executable internal
component joins normal VR input, actual native history and original PCM, but
it cannot establish a physical microphone, acoustic playback, an independent
peer result or the entire fourteen-checkpoint shared Audio journey.

`PicoBoundAdapter._audio_preview(target, run)` composes
[`AudioPreview`](../audio_preview.py), the existing candidate/PID/start/OpenXR
binding, [`PicoAudioIO`](normal_audio.py), `TokenAudioUI`,
`NativeFeatureObservation` and `RecordedPreviewEvidence`. It requires the
existing explicit normal-Scripts fixture configuration because the original
Pico VR navigation transport is shared. It neither discovers nor repairs a
session, changes permissions, starts an external service or launches a client.

The component's caller already owns a normally opened Audio page, selected in
its actual current VR mode. `claim()` accepts only an independently measured
native cycle-zero/history-empty state with no separate file recording, actual
empty E2E memory/files and an
agreeing original VR page. Existing unowned terminal history cannot be reset
by releasing PCM. The component does not change live echo, the selected mode,
page ownership, the original permission or any other user's recording.

## Executable operations and original observations

| Internal operation | Input and actual observation |
| --- | --- |
| `claim()` | No input. Pin installed candidate, process/start, session, source instance, UI root/generation and original mute from separate actual sources. |
| `act(operation_id, 'record-start')` | Persist unique operation and original token/cycle before one normal Record activation. Require exactly one original native cycle increment plus agreeing original page/record metadata; return the actual phase, including a real rejected Start error. |
| `act(operation_id, 'record-cancel')` | Activate only the current owned active cycle's normal Record/Cancel button. Its original cancelled history and empty live buffers are mandatory; natural completion cannot qualify cancellation. |
| `act(operation_id, 'mute', enabled=boolean)` | Normal mute toggle only when current original state differs. Actual native/UI mute and any resulting recorded-preview cancellation/error remain measured effects. |
| `read()` / `await_terminal()` | No product input. Preserve original complete native event prefixes, times, historical frame format and non-regressing live counters. Independently acquired UI/native samples may straddle a real transition; bounded rereads join them without manufacturing a phase. |
| `originals()` | Read original pre-normalization input PCM and separate native accepted-write PCM with their original hashes. Require exact same source instance, cycle, native Start time, format and full original event history. Return unchanged original bytes and original acquisition metadata. |
| `reconcile()` | After a lost input result, read only. Resolve a delivered Start/Cancel/mute only from its exact actual effect. Never resend. An ignored Start or natural completion after an uncertain Cancel keeps unresolved ownership. |
| `release_native()` | Cancel only a currently active owned cycle through normal input, restore original mute, observe actual product quiet for three seconds, release native E2E taps and separately inspect real memory/files, then sustain another three-second product-quiet interval. |

Every operation holds one existing OS-backed source lock for the complete call.
Reconstructed CLI/controller objects read the same private mode-0600 journal,
validate its complete candidate/process/run scope and preserve source cursors.
Input intent contains the original token and cycle before actual delivery.
Completed operation IDs cannot be reused. A bounded archive retains original
terminal histories and acquired PCM metadata across later normal cycles. Actual
PCM bytes returned by `originals()` must additionally be retained by the owning
runner in private artifact storage before another cycle or the native lease
expires; journal hashes do not replace those original bytes.

The normal UI primitive bounds its input/readback to ten seconds and at most
seven actual scrollbar advances. Independent native/PCM transfers retain their
five-second source bounds. Source joins use ten seconds/101 observations;
terminal waiting uses fifteen seconds/151 observations. Each quiet interval is
three seconds, bounded to five seconds/51 samples. Journals allow 32 operation
records, 16 original input intents per outstanding operation and at most eight
archived terminal cycles; the existing 64 KiB private-state limit also applies.
Exhaustion fails closed and preserves the previous unresolved journal.

A missing Release result leaves `releaseState: requested`. A later call performs
only a fresh read-only actual memory/files query; it never sends Release again.
An ACK with retained files, nonempty memory, changed process/candidate, foreign
cycle, rewritten history or a missing source cannot qualify release. The native
history and PCM taps now use the same original Start timestamp; reads never
retime either source. See the [native PCM contract](../../native/RECORDED_PREVIEW_EVIDENCE.md).

Even after `releaseState: verified`, this component deliberately retains its
journal and original terminal history. It cannot restore cycle-zero by clearing
instrumentation, and it has no journal-discard method. Final adapter-wide
cleanup must join independently observed old-process death, a verified restart
with actual idle native history, original page/settings restoration and drained
external stimulus/recorder/publisher roles before retiring ownership. That full
area coordinator is not implemented by this component.

## Remaining complete-area boundary

The next executable work is a separately owned, explicitly configured fixture
stimulus/acoustic-recorder process and independent publisher. It must start from
the current recording ticket, deliver the short `recorded-preview-v1` challenge
to the real microphone path, and retain the separately recorded output bytes,
source format, physical capture-point identity, process/route ownership and
original acquisition times. The existing digital voice-peer roundtrip source
cannot stand in for that physical path. No source copies expected challenge
samples into a result; native sink-write PCM is not an acoustic recording.

Then compose normal Audio open/close, mute and background interruption, original
permission/echo restoration, the existing one-send native restart framework and
independent per-role final restoration/quiet/resource checks with the shared
journey. Extend the private scope to the fixture ticket and each owned external
role before advertising any complete area triple. Current factory scope binds
the run and actual native cycle, not an acoustic challenge ticket. Adapter-wide
cleanup attempts the known native release and preserves this component's
outstanding journal, then reports failure even after base process teardown.
A stopped process cannot complete its missing final restart/role join.

## Focused verification

Run only the explicit entries below with `PYTHONDONTWRITEBYTECODE=1` and an owned
private `TMPDIR`. No broad quick/full catalog or device service is required.

```bash
python3 tests/device/self_tests/test_audio_preview.py -v
python3 tests/device/self_tests/test_recorded_preview_evidence.py -v
python3 tests/device/self_tests/test_recorded_preview_history.py -v
python3 tests/device/self_tests/test_token_audio_ui.py -v
python3 android/vr/pico/tests/device/test_audio_preview.py -v
python3 tests/device/contracts/audio/test_recorded_preview_observation.py
python3 tests/device/validate_contract_versions.py
python3 android/vr/pico/tests/pico4-coverage-test.py
python3 tests/check-documentation.py --all
git diff --check
```

Seventeen component counterexamples execute the real owner, private state/lock,
TokenAudioUI and native/PCM readers against explicitly synthetic independent
boundaries. They cover completion, cancel, muted rejection, mute interruption,
source joins, old/foreign/rewritten evidence, lost input results, nonreplayed
uncertain actions, native release, retained files and retained journals. Two
Pico cases additionally exercise the actual candidate wrapper, normal native
navigation-token input and private byte transport, including candidate-loss
refusal before cleanup input. Separate existing wrapper cases retain stale
token, ignored input and missing producer checks.

The narrow compiled check uses the actual E2E observer with Qt Core and an
explicit QAudioFormat value seam. It excludes AudioClient, Qt Multimedia,
Android and OpenXR. The complete native client remains uncompiled by this
packet; devices and acoustic paths remain untested. Later actual device
qualification must use the Proxmox Jenkins laboratory.

# Partial iOS normal recording ownership

`IOSAudioRuntime.recorded_owner` binds the existing installed candidate, SDK,
foreground process and shared Script source lock. The [version-three page
composition](AUDIO_PAGE_CYCLES.md) can now open and restore the ordinary page
within this same owner. It constructs the existing `IOSAudioIO` / `TokenAudioUI` input recipe;
it does not call a synthetic audio Start/Stop command.

`IOSAudioRecordedOwner.act(ticket, verb)` supports `record-start` and
`record-cancel` for the actual active Audio fixture ticket. Immutable original
frames retain the UI source, original native recorded-voice history, separately
queried native clock brackets, and unchanged fixture activation metadata.
Host UTC and monotonic clocks bound acquisition; they never replace native
capture times. UI acknowledgements and requested values are not measured
recording effects. Cancellation requires two newly acquired native cancelled
observations separated by at least 300 ms, with empty native live counters.

The [version-2 normal cycle extension](AUDIO_NORMAL_CYCLES.md) adds actual
mute/unmute inputs, original muted Start rejection, cancellation by mute and
no-input automatic completion. Literal-1 owners/observations remain readable.
The connected new host flow joins completion to the existing original PCM lease;
it does not claim independent acoustic output or complete Audio cleanup.
The same 25-second host API budget spans nested owner calls and final transport
guards; each original acquisition retains its separate 1.5-second clock bound.

The private CAS journal retains the candidate/run binding, input ticket, cycle,
original frame references, actual query IDs and original token input intents.
Each normal input intent is committed before delivery. Lost results remain
pending. Reconstruction may read new originals to resolve the exact owned
cycle; it cannot resend the input. An ignored input remains unresolved.
Interrupted evidence storage can recover a complete inode-bound original;
missing or partial originals remain unresolved and are never recreated.
`archive` decodes retained originals under the real lock without live getters.
Completed cancellation retains and reopens both original quiet samples. Lost
owner metadata cannot turn existing Audio original carriers into a new run.

This is an internal partial adapter packet. It does not activate an Audio
capability or change the feature configuration. It does not allocate original
PCM tap snapshots, remove tap files, assert independent acoustic output, or
retire process/SDK ownership. The new normal page/cycle/PCM composition keeps
those responsibilities separate. The full shared Audio scenario still needs
loaded code/settings ownership, independent acoustic/Actor evidence, permission
and background recovery, weak page/resource retirement and final cleanup
integration. Empty native recording counters do
not establish absence of an independently allocated tap snapshot.

The focused host tests use real private journals, OS locks, immutable original
files, normal input recipes and typed native/fixture validation. UIKit, audio,
installed process and fixture transport boundaries are explicitly modeled.
Native compilation and device qualification remain unexecuted.

The twelve selected host tests pass in 3.986 seconds, including ignored or lost
input, changed native birth/history, missing originals, deleted owner metadata,
and requested sleep without measured quiet. The five no-build project suites,
contract-version registry and whitespace checks pass. The focused command is:

```bash
PYTHONPATH=.:tests/device:tests/device/self_tests:tests/device/ios/self_tests python3 -m unittest -v -f test_ios_audio_recorded_owner.AudioRecordedOwnerTests
```

The local run additionally used the private `TMPDIR`,
`PYTHONDONTWRITEBYTECODE=1`, the no-build verification overlay on `PYTHONPATH`,
and a unique `OVT_IOS_BLOCKED_ATTEMPTS` path. No blocked attempt was recorded.

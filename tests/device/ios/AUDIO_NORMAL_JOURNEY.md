# One ordinary fourteen-action Audio composition

The existing recording owner, current authorization child, PCM lease and
same-process interruption child now have one connected host case following all
14 actions of the unchanged shared Audio scenario. It uses their existing
runtime factories and normal input codecs; no separate Audio controller,
public feature dispatch or capability is introduced.

The composition opens the actual modeled page, mutes, observes an originally
rejected muted Start, unmutes, records and cancels, then records another cycle
through automatic playing/draining/completion. All five Starts pass through
the [current OS authorization owner](AUDIO_AUTHORIZED_START.md), including the
Start that is rejected by native mute despite an original OS grant. Independent
before/after authorization originals retain their own native and host clocks.

The completed third cycle supplies its exact original input/sink PCM lease,
which retires independently before later cycles. Ordinary mute cancels the
fourth cycle. The fifth cycle is cancelled by the existing actual OS-input
codec and its separately observed same-process background/foreground child;
the canonical parent bridge then permits normal page and mute restoration.
The test derives each scenario state from validated native/UI originals,
never from requested inputs or their acknowledgments.

The final case passes in 104.367 s. Pure reconstruction then reopens recording,
authorization, authorized Start and PCM owners without additional native,
permission, PCM, page or OS calls. All 131 retained fixture files have identical
bytes, device, inode, size, mtime and ctime before/after that reconstruction.
The initial composition also passed in 104.855 s before the explicit complete
file census and later-cycle memory assertion were added.

Later cycles deliberately retain newly allocated modeled PCM evidence memory.
The retired cycle-three lease remains an exact historical proof for cycle
three; it supplies no resource-absence claim for cycles four/five. Closing the
page does not retire the Audio session barrier or its source journals.

Four unchanged default/background/page/PCM and literal-version-three cases
also pass in 14.361 s. The existing background fixture's default preparation
still performs its original Open/Start; the new composition explicitly selects
an initially closed, unprepared owner through that same fixture.

These tests execute actual private files, CAS, original codecs and normal
operation composition. Audio, Qt, SDK, OS, automatic timers and clocks are
declared host models. No independent acoustic microphone/speaker, Peer, native
compilation, device or real-CPU whole-journey budget is qualified. Required
acoustic/Peer artifacts, loaded code/settings/page/callback retirement,
permission-driven process replacement and the paired process/SDK end remain
open. The full Audio capability stays disabled.

The explicit no-build entrypoint is:

```bash
PYTHONPATH=.:tests/device:tests/device/self_tests:tests/device/ios/self_tests \
  python3 -m unittest -v -f \
  ios.self_tests.test_ios_audio_normal_journey.AudioNormalJourneyTests
```

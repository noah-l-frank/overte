# Owned recording cancellation across ordinary iOS background and resume

The installed Audio runtime constructs an interruption child under the original
recording owner's source lock. The parent remains byte-for-byte unchanged. A
completed owned Start, original active cycle, current Audio controls and a new
foreground native/UI cut are mandatory. A different active recording cycle
cannot borrow that Start. Its fresh before cut expires after 1.5 seconds before
the OS input; a recovered old cut cannot authorize a later Home action.

The child uses the existing [background-safe OS context](LIFECYCLE_BACKGROUND.md).
Actual process/source observations bracket the app-state query and preserve
the original installed candidate, PID and SDK. Its private CAS journal records
each issued phase before ordinary `mobile: backgroundApp` and activation.
Uncertain returns never repeat those inputs. Ignored inputs remain owned.
Recovery while backgrounded constructs no native or UI source; only an actual
foreground observation permits the source factory. No SDK session is created
and no process is launched. The existing 25-second Audio API budget applies.

After foreground, two immutable acquisitions at least 300 ms apart on both
native and host clocks must show the same owned cycle cancelled, the original
event prefix, empty live recording buffers and a real `backgrounded`,
`lifecycle-stopped` or `input-or-lifecycle-changed` native reason. Native
background/activation counters advance while launch and ordinary input counters
remain unchanged. Native sample clocks retain their original offset from host
UTC. Zero buffers establish neither acoustic silence nor audible playback.

The child retains every issued readonly query ID, its original before/after
packets and independent clock joins. A saved original interrupted before its
reference append is adopted with its exact original bytes and inode; no new
native cut or OS input substitutes for it. Failed observed outcomes remain
owned. Historical repeat results carry no new sample time; reconstruction still
checks the existing OS context and never implies SDK retirement.

The initial 49-case selection passes across interruption, recording, admission
and existing Chat background integration. The final sixteen interruption cases
also cover native relaunch under the same PID, stale saved-before input refusal,
foreign recording cycles, lost/ignored OS calls, failed intents, source/PID and
parent substitution, retained capture and wrong cancellation reasons. These
exercise actual private files, CAS, locks, original codecs, installed guards and
normal OS request paths. Audio/UIKit/SDK/native clocks are explicit host models;
no build, device, permission or acoustic qualification follows.

This is an interruption component. The [version-four parent bridge](AUDIO_BACKGROUND_BRIDGE.md)
now joins these exact originals to a fresh foreground parent cut, preserving
lifecycle equality everywhere else. Full Audio also needs independent
Actor/acoustic/permission evidence and complete settings, page, callback, source
and process/SDK retirement. Its complete capability remains closed.

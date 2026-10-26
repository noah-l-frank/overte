# One Audio owner from ordinary opening through page restoration

The existing installed `IOSAudioRuntime.recorded_owner` now constructs version
3 of the same recording owner. It also reads literal owners/observations 1 and
2, preserving their input boundaries and original files. No parallel recording
manager, new transport or native product behavior is introduced. The full Audio
capability remains closed.

`act(ticket, 'open')` requires the actual closed tablet or observed launcher and
inactive native recording. Normal toolbar, observed pagination, direct AUDIO or
SETTINGS/Audio controls enter the actual page. Every resolved element/token and
original UI input snapshot is durable before its single click; returned ACKs
are recorded separately. The actual first launcher selection is retained.
Ordinary mute input prepares the required unmuted baseline and preserves the
original native mute value for restoration.

Normal recording, muted rejection, cancellation by mute, unmute and automatic
completion use the [same version-two cycle proofs](AUDIO_NORMAL_CYCLES.md).
The original PCM lease links to the actual owned Start and requires independent
file/memory absence before page close when a lease journal exists.

`act(ticket, 'close')` rejects active recording or an unretired PCM lease before
any page mutation. It restores the initial native mute value through normal
input, goes Home, restores the actual original launcher page and closes the
tablet. Two new immutable originals at least 300 ms apart in native and host
time verify closed visibility, inactive voice and restored mute. The exact
opening-before/after references are validated as earlier owned membership.
Only the new page profile admits up to 72 navigation inputs and 1,024 pending
readonly queries; recording operations retain their existing 16/256 limits.
The common file/pack, acquisition and 25-second API bounds remain unchanged.

Lost entry or final Close results are resolved from new actual UI/native
originals without another click. Ignored entry stays owned. Original ACK
uncertainty remains visible in the input journal; current page visibility does
not fabricate a successful SDK return. Saved source bodies, clocks and native
recording history remain immutable, including on pure archive replay.

The 63-case focused page/cycle/error/legacy/PCM selection passes. Three more
close/archival counterexamples pass in the seven-case final page selection,
including a live PCM lease preventing close and a lost final Close. Tests use
actual private files, CAS journals, locks and ordinary W3C/Audio codecs. Native
audio, Qt/UIKit, SDK, timers and clocks are explicitly modeled; devices and
native compilation remain unverified.

This proves normal page navigation and mute restoration, not whole settings
restoration or weak-object/callback death. All journals and originals remain
owned. Still required are actual loaded Script/QML and setting ownership,
microphone authorization, background/permission recovery, independent acoustic
and Actor evidence, original page/resource quiet and paired process/SDK end.

The [session ownership barrier](AUDIO_SESSION_OWNERSHIP.md) preserves these
unfinished responsibilities before ordinary SDK work. Closing this page or
retiring its PCM lease cannot bypass that barrier.

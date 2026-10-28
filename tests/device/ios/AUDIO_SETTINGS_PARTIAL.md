# Partial typed Audio settings originals and normal Mute/Echo restoration

All sixteen selected host cases pass in 27.742 seconds. Native compilation,
thread dispatch, Qt serialization, hardware and devices remain unverified. This
is the next small vertical component for Feature9/14, not complete Audio
restoration or feature completion. The complete adapter count remains 5/14.

The actual source reveals an existing side effect: Audio::setMutedDesktop(false)
and setMutedHMD(false) disable their corresponding push-to-talk setting once
settings are loaded and the user is not currently pushing. The iOS TouchUiProfile
sets pushToTalkAvailable=false, hiding the ordinary PTT control. A direct setter,
hidden control, synthetic configuration or successful click cannot supply a
normal restoration path for that setting.

The new owner therefore refuses active PTT in either context, unloaded settings,
pushing-in-progress, mismatched current mode, active recording or mismatched
Script/client mute before any mutation. Admission belongs before the existing
recording owner's Open/unmute. This is a mandatory order for the new explicit
composition; existing legacy partial APIs remain unchanged and do not gain a
whole-settings capability through this child.

## Actual typed source

The dedicated iOS E2E/voice build adds a read-only Audio owner method and exact
nonce-only native getter. Audio fields and persisted Setting handles are read
on the Audio object's thread under its existing read lock. Client mute, local/
server echo, stereo and recording state are read on the AudioClient thread.
Avatar/server-injector gains are read on the actual NodeList owner thread,
without holding the Audio lock across that call. No setting is written, saved,
loaded or reset. No microphone, acoustic or permission success is inferred.

The getter retains two sequential reads of each typed source and rejects
unequal values, lifecycle or current-mode change. Two equal reads do not prove
an atomic cross-thread snapshot, absence of an intervening ABA change, or the
absence of a deferred setter. Original before/after clocks retain the existing
1.5-second acceptance bound; blocking native calls do not acquire a new hard
real-time cancellation guarantee.

The source includes both context Mute/PTT values; current push state; noise,
AEC, warning, threshold and input volume; local/system/PTT gains; cached typed
persistent values; client local/server echo and stereo; and mixer avatar/server
gains. Those are exactly named observed operands, not every device route or all
Audio/OS preferences. QJson numeric values are checked as finite numbers and
booleans remain literal booleans. Missing fields, requested expected values,
future versions and unequal reads fail closed. Source lifecycle/instance/PID
must follow the original canonical clock brackets.

The nonce is consumed once by the existing Probe. The new file uses the existing
voice-build writer gate, compact byte bound and private atomic QSaveFile path.
The source frame collector reuses existing OriginalFrameStore and FileSources:
query intent precedes sending, literal AFC/native-clock bodies remain retained,
raw prefixes and unknown delivery remain owned, and saved immutable originals
can be adopted without another query or input. All source namespaces stay under
the existing ios-audio session barrier. No source artifact retires that barrier.

## Restricted normal-input child

IOSAudioRuntime.settings_owner constructs the child beside the existing
recording owner, using its actual lock/binding and a freshly verified existing
session. The explicit sequence is baseline before normal Open, the existing
ordinary journey, selected-value restore while the real Audio page is still
open, then the existing normal Close and one more typed verify. The child does
not create a WebDriver session, replace the installed process or activate a
public feature route.

Only the current context's native Mute and local echo may differ from baseline.
Every other captured runtime/persisted/client/mixer value is an exact drift
guard. Full guards and current capability are reread before each normal input,
including scrolling or selecting the actual current mode. Unowned changes stop
the operation rather than being overwritten. The final selected values and all
captured guards must exactly match their originals.

Each operation keeps its original `admittedBefore` reference while separately
capturing a fresh `before` cut. Both selected values must equal that admission
before navigation or input. After delivery, only the named selected target may
change. Decode repeats these typed original/value/order checks. This preserves
the admission across the owner's runtime writes; it does not independently seal
the mutable WAL against coordinated rewriting of consistent original references.

Existing TokenAudioUI and IOSAudioIO deliver the original normal control token.
Original input UI, before-settings reference and navigation intents are durable
before delivery. An ignored click stays pending even when its return arrived.
A lost return stays false; only a new typed original establishing its exact
value may resolve the effect. No click is retried from a pending intent. A
change in the other selected value during one input also prevents resolution.
If navigation outcome or a pre-dispatch admission is unresolved, its ownership
remains; this small child provides no synthetic repair or resumed click.

`observedSelectedMuteEchoValuesRestored` means only that those original values
were freshly observed again under all the named guards. It is not full setting
ownership/weak-object/callback death, disk persistence restoration or source/
process/SDK end. wholeSettingsRestorationAvailable,
independentAcousticsAvailable and processSdkRetirementAvailable remain false.

## Host counterexamples and open requirements

Twelve existing packet cases use real private files, exact raw/source codecs and ordinary input
primitives with explicitly declared Audio/Qt/clock producers. They cover exact
Mute/Echo restoration, ignored and lost input, both-context PTT refusal before
input, runtime/persisted/mixer/echo/stereo drift, malformed typed or unequal
reads, saved adoption, unknown query intent, replaced inode/current guard loss
and readonly verification. Four additional cases cover fresh-token preparation/scroll drift,
reconstruction after a lost input return and refusal of an admission reference to
an actual post-effect original. All sixteen run without skips within the fixed
120-second outer bound and five-second kill grace. The original 1.5-second
native acceptance, 25-second owner, five-second file and 32768-byte AFC limits
are unchanged. All 5,961 source/launcher/dependency pins and 284 retained files
in sixteen actual fixture roots agree, with matching post-stop censuses and
no remaining owned processes. Earlier startup guards refused two invocations
before target imports: an unrelated build-directory namespace and inspection
of an unimported namespace parent. Those logs remain retained; no test result
is attributed to them. The corrected runner uses three actual device-source
roots and the locally reviewed CPython namespace-spec collector without
importing parent packages. Adapter/test bytes did not change for these fixes.
These declared Audio/Qt/clock models qualify no native Settings, UIKit, thread
dispatch, actual audio hardware or complete shared journey.

Full Audio still requires every mandatory original setting and a real ordinary
restoration path for active PTT or an explicit product capability decision;
permission-driven process replacement; independent acoustic and Peer/Actor
artifacts; loaded code/page/callback/source ownership; and paired process/SDK
end. The prior fourteen-action host composition does not transfer qualification
automatically to this new source revision.

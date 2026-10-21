# Phone Emote cleanup input ownership, version 1

`PhoneEmoteCleanup(PhoneEmoteInputs(source))` is the cleanup-phase owner of
ordinary chooser/SDK inputs. The real source must be primary, current, held by
the existing source lock and bound to the same candidate/process/run/fixture.
This module supplies no complete feature capability. Its result establishes
native/UI restoration only; selected/unknown timer quietness, scene/view/browser,
GPU buffers, actor and host-file retirement remain separate mandatory checks.
The native source is uncompiled and all device behavior remains untested.

`cleanup({contractVersion:17,runId}, sleep=...)` requires the actual current
fixture activation to be `cleanup` with empty inputs. The actual ticket is read
from that activation. The stored call contains exactly the public cleanup keys
plus that ticket. No normal `cancel`/`close` activation, call or acknowledgment
is fabricated. Old normal input journals remain byte-for-byte owned, including
their interrupted input phase; cleanup records their observed reconciliation
separately. The shared `PhoneEmoteInputTransport` contains the same one-send
SDK/Qt primitives and original chain checks as normal inputs (wire version 2
unchanged), with an additional cleanup ownership check at the actual cancel
barrier before any toggle can be sent.

The original primary namespace-zero source must exist. Its first original frame
must observe the real baseline phase, a closed tablet/absent chooser and inactive
native override. A user-owned originally open tablet cannot be adopted. Current
source frames/manifests, normal input originals and the original baseline are
reopened and checked before cleanup. An interrupted normal history archive,
missing originals, changed control/binding or stale in-memory state blocks
cleanup without deleting responsibility. The enclosing owner must resolve source
acquisition/observation transfers and OS foreground recovery first.

For an active native override, cleanup finds the last actual normal play/Sit/
replacement Qt intent and its original pre-input native barrier. The current
source must select the same original manager/compiled caller. Exactly one new
native override after that barrier must match the ordinary button, actual
native generation and controlled asset URI. A different caller, later unowned
override, different native asset or mismatched active chooser name prevents a
toggle. Failed animation loading may still require cleanup, so this ownership
join deliberately makes no loaded/moving/image feature-success assertion.

The owner stops only that owned generation by toggling its actual active chooser
button, closes the chooser through normal Home, then closes the owned tablet
through the existing SDK path. Every intent is durably written before dispatch;
every consumed Qt receipt or observed SDK transition is retained. During retry,
a lost Qt return is accepted only when a new independent source observes the
exact consumed input sequence in the same native/UI incarnation. A lost SDK
return requires the actual intended visibility transition from its original
before frame. Uncertain/ignored input is never resent. A queued cancel with a
consumed receipt must not cause a second toggle while its native return is late.

Final verification obtains new original source frames. It requires actual UI
absence, native inactivity, original Rig/history continuity, no new override and
unchanged lifecycle during this cleanup. An initially active generation needs
the original selected native restore and at least three actual inactive evaluated
frames; no expected duration, chooser acknowledgment or expected state replaces
those observations. Final acquisition polls at most 32 times with 100 ms gaps;
the whole operation has a 45-second monotonic bound, in addition to source/SDK/
Qt/fixture limits. A successful retry still reads fresh originals. It cannot
return a cached completed result after native activity resumes.

The private control file `phone-emote-cleanup-inputs.json` contains exactly
`emoteCleanupInputsVersion:1`, `runId`, `fixtureUrl`, `binding`, `artifactRoot`,
`segment`, `payload`. The bounded existing packed payload holds one
`{current,origin,normalRecovery,final}` state. `origin` hashes the unchanged actual
normal input header (including an absent header). `current` is
`{call,phase,before,intents,idleReset}` with phases acting/issuing/acknowledged;
`idleReset` is always null. Before/recovery/final and native barriers reference
actual source frames by original revision/hash. Intent chains use the existing
closed Qt/SDK format and 64-intent limit. Final is absent until independently
verified. The enclosing owner must retain this original proof before verified
whole-run retirement; this module never deletes its control or source originals.
General Phone cleanup refuses a remaining cleanup-input control file.

Host counterexamples cover ignored inputs, lost Qt/SDK returns, interrupted
normal delivery, foreign callers/assets/UI, absent source originals, wrong phases,
changed cleanup tickets, failed intent persistence and fabricated final frames.
They qualify only adapter/test logic over synthetic boundaries.

# Common feature journey migration: current version 7

## Version 6 to 7: actual Chat channels, local fallback and explicit resend

ArmoredChat provides Local/Domain tabs and bounded separate channel histories,
not a peer filter. Its QML clears the draft when sending and destroys an unsent
draft when closing the owned page. MessagesClient without an active MessagesMixer
emits local-only echo; the unchanged Chat script stores that echo. No offline
error banner, retained draft, automatic queued retry or remote ACK exists.

Version 7 adds localMessages/domainMessages/peerMessages, actual channel and
mixerConnected. messages is the current original visible channel model when
open and empty when closed. Stored histories remain measured when closed, using
the original persisted history, not a recreated expected list. peerMessages is
read from actual owned remote peer reception; local echo/native sends cannot
populate it. Both primary and independent observers acquire original sources
separately. The independent projection also includes open so row visibility is
validated against the observed page, not the closed baseline prototype.

Twenty-four checkpoints replace the previous sixteen. A cancelled draft creates
no peer delivery. A Domain arrival while Local is selected stays in Domain
history; a distant Local sender is rejected without adding a row. Offline Send
requires actual disappearance of the owned MessagesMixer before input; it clears
the draft and adds one local Domain row but zero remote rows. A three-second
restored-mixer/no-replay window precedes explicit retyping and resend. Afterward
the actual local history contains two retry copies, the independent remote
ledger exactly one. Close/distant/removal/restoration/no-replay observations use
three-second negative windows, never a single early empty snapshot.

There were no qualified complete v6 producers. v7 rejects old inputs and removes
filter-peer/network-disconnect/back from Chat's closed vocabulary. No product
change, capability promotion, build or physical qualification is implied. Other
area semantics and independently versioned native/fixture transports remain
unchanged. See [the exact source and adapter prerequisites](CHAT_SOURCE.md).

## Version 5 to 6: view dismissal, retired responses and actual delayed authority

Closing the login view deliberately does not cancel AccountManager's request.
This is explicit in PhoneLoginState and consistent with generic LoginDialog/
overlay/tablet destruction. Version 6 observes pending=true after close and
reopen, without submitting twice. It then closes the view and performs an actual
app restart before the fixture releases the old grant. New native process/source
identity and actual lifecycle counters must change; no input ACK or view close
can stand in for this boundary. Optional anonymous startup prompts are observed
and dismissed through the ordinary idempotent login-cancel action.

The new measured boolean delayedGrantOutstanding comes from the fixture's
actual retained access/refresh authority for a real held request. It becomes
true only after actual valid credentials were issued, and stays true through
native logout until separate controlled fixture revocation. Thus a server
503/expired hold or an ACK without a real old success cannot pass the stale
response checkpoint. Native logout makes the current client anonymous; it is
not claimed to revoke remote tokens. Fixture cleanup blocks new grants,
cancels held handlers and revokes issued authority before baseline/quiet checks.

The independent Authentication witness now measures all six fields: principal,
dialog, error, pending, protectedAccess and delayedGrantOutstanding. It must
acquire actual UI/error state too; a primary error echo with unchanged backend/
UI cannot pass invalid login. Neither actor nor adapter receives expectations.
The public sanitized delayed-grant endpoint returns original request identity/
times/status and fresh actual authority validity, without credentials. Consumers
pin provider/run, retain original records and reject missing/rewritten history.

Account provider version 2 holds the real server request for at most 90 seconds
so an old consumer can be retired and a new process can start before release.
The native client's unchanged 15-second token/profile deadlines still apply
while it lives. Preserve a genuinely pending old request before restart and
prove actual valid issuance afterwards; a native/server timeout is insufficient.
The source fixture itself is not native UI, native trust or a complete actor.
Clean current native probe/origin scopes before intentional restart, then
acquire the independently verified new context; never copy old ownership into
it. Controlled provider arming/release/revocation are reader-side stimuli bound
to the current closed action, not product-state setters or desired facts.

Seventeen Authentication checkpoints replace the previous twelve. Other area
flows retain version 5 semantics. Full native UI/action/actor/restart producers
remain incomplete, native instrumentation is uncompiled and device qualification
is absent on every platform.

## Version 4 to 5: ordinary Emote effects, completion and early restoration

Ordinary Emote playback uses the actual native animation override too. Version 5
requires override:true for ordinary plays/Sit and real loaded, advancing native
pose/peer/image effects. A selected name or chooser highlight is insufficient.
The chooser can be hidden on the reviewed Phone source or retained on the other
reviewed sources. Its initial open and final close remain definite; play inputs
must reopen the actual chooser through ordinary controls as needed, using the
actual submitted startup-source profile. No visibility setter or script handler
may stand in for that input.

Each of the nine non-Sit clips now has a closed `wait-complete` action with empty
inputs. This action sends no product input and invokes no animation restoration;
observers wait for the existing source's own completion and an evaluated idle
pose. Sit is different: the ordinary tablet source holds its final pose, while
the Phone source uses a one-shot timer. Sit resets/variant discovery therefore
allow either actual restoration timing and make no early-abort claim. The
original undefined tablet Sit end-frame argument remains an unresolved source
concern; no replacement frame count or functional fix is injected.

The explicit replacement Waving clip must then be cancelled and independently
show `restoredBeforeNominalEnd:true`. This new measured boolean is false without
an owned prior run or with ordinary nominal completion. For the owned run, it
requires the original override range/rate, matching original restore event and a
later inactive evaluation, with restoreEpoch - overrideEpoch strictly below
1000 * (lastFrame - firstFrame) / framesPerSecond - 250ms. Range/rate/times must
come from actual native history; unknown, stale, dropped or invalid sources are
unavailable, never a guessed false. A new ordinary play resets the owned-run
association; cleanup clears that association only after real restoration.

This flag describes timing, not a button/timer cause. The complete producer must
also correlate original normal input, selected submitted-code profile, actual
loaded clip, changed evaluated poses and fresh current image/peer effects. The
independent observer must acquire/check its own original native timing facts in
a serialized observation phase plus actual replicated pose effects. It must not
copy adapter state or a requested result. An input ACK, native request count or
late natural completion cannot satisfy the explicit abort. Native original
clocks must remain distinct from iOS host epochs. The actual history helpers
supply narrower prerequisites, not this complete coordinator.

Current actions, observations, registry and generated files use contractVersion
7. Only version 7 requests are accepted; versions 1..6 have no qualified complete
producer and remain in Git history. Current files are adapter-contract.v7.json
and coverage.v7.json. Observation schema 1, resource/journal transport v1 and
independently versioned native primitives remain unchanged. The account fixture
is independently versioned 2; it does not relax native OAuth deadlines or TLS.


## Historical version 3 to 4: immediate Graphics controls and measured originals

Version 4 replaces the fictitious universal preset-preview/Apply/Cancel and
shadows-on/resolution-1.0 assumptions with actual ordinary resolution, Haze and
Mirrors controls. Phone accepts 0.5..0.7 in 0.05 increments; the common settings
page accepts 0.1 increments. The shared inputs 0.5 and 0.6 work on both actual
surfaces. This changes the viewport-resolution control, not Pico's separate
restart-confirmed runtime-eye-resolution selector. No functional UI is added.

Graphics `baseline` values in scenarios.py are type prototypes. Before any
input the runner obtains a fresh original product state, pins its six declared
`measuredBaselineFields`, then requires stable fresh matching product and
independent actor observations. The dialog must initially be closed. Original
values are runner-local evidence; they are never sent as expected state or
input to adapters/actors. Unverified, moving or foreign-open baselines cannot
admit an action or cleanup of unowned resources. The adapter independently
persists its own original preferences and process binding before modifying them.

Expected checkpoints retain original values until each setting is changed.
Closing the page, background/resume and verified restart must retain immediately
applied settings. Haze and Mirrors are toggled both ways, ensuring at least one
real effect even if already enabled. `restore-original` accepts no values and
must use the adapter's own measured originals. Final double cleanup must restore
the runner's independently frozen originals, not a hard-coded default profile.

`resolution` is the original requested viewport setting; `renderScale` is an
independent actual completed frame's render-target/viewport ratio. `haze` and
`mirror` are actual settings, while `hazePass`/`mirrorPass` require actual rendered
pass evidence in the controlled visible subject. Native settings reads do not
prove those fields. Original challenge-bearing world pixels additionally prove
resolution and visible effect changes; no UI screenshot or painted marker can
substitute. The [owned Graphics subject](GRAPHICS_SUBJECT.md) supplies versioned haze/reflector
geometry and a current-ticket world marker. View/lighting must remain stable.
Native render acquisition and the full fixture source/input/observer join remain
prerequisites before platform activation.

At that stage only complete version 4 producers were accepted; prior versions 1/2/3 had no
qualified producer and are rejected. Current inventory/matrix are
`adapter-contract.v4.json`/`coverage.v4.json`, with observation schema 1 and
resource/journal transport v1 unchanged. Native primitive contracts remain
independently versioned. This correction grants no full-area capability and no
device acceptance. Platform Emote semantic corrections were still open at that stage.

## Historical version 2 to 3: actual recorded preview

Version 3 replaces the draft manual Audio Save/Preview/Stop transaction with
normal automatic three-second in-memory capture/play/drain/completion. It adds
actual phase/history, played-frame and live-buffer observations, rejects
impossible combinations and requires a whole completed native cycle with equal
captured/played frames and empty product buffers. A muted Start and mute or
background cancellation are tested through real user controls/lifecycle.
The existing composed `permission-recovery` foundation retains OS permission
checks; these are not replaced by an invented preview permission dialog.

`await-completion` is a bounded observation wait, not a new product control.
There is no client Save, Preview Start/Stop or Discard input on this surface.
The `file` evidence is lossless original input PCM acquired through dedicated
E2E instrumentation, not a user-exported recording. Independent acoustic PCM
must prove actual output separately; accepted native writes alone do not do so.
Both carry the three-second `recorded-preview-v1` challenge from that Start,
with actual native cycle/original event/byte provenance. Old source times must
not be relabelled as new recordings. The old `voice-v1` fixture is unchanged.

At the version 3 stage, requests, observations, engine, registry, generated inventory and matrix
used `contractVersion:3`; observation `schemaVersion` and the independent
`/feature-fixture/v1` resource/journal transport stay unchanged. No qualified
version 1 or 2 complete platform producer existed. Prior requests/observations
are rejected; current files are `adapter-contract.v3.json`, `coverage.v3.json`.
Native Script/preview primitive contracts and the narrower foundations remain
independently versioned and unchanged. All devices remain untested.

Cleanup must close owned UI, observe inactive/empty native buffers, release and
separately observe absence of owned E2E evidence, and restore the original mute
state. Because the real native status retains its terminal history, restoring
an initial idle/history-empty baseline requires a real verified application
restart and new native context, not an instrumentation reset of product state.
This restart handoff and the normal Audio input/independent actor joins are
still required in the complete platform adapters.

The existing Graphics and platform Emote source mismatches still block those
area producers. This migration does not activate any full feature capability.

## Historical version 1 to 2: Script import

Version 2 corrected the Scripts user flow exposed by source review. Client URL
and file loads do not have the entity-script consent transaction assumed by
the original version 1 draft. That shared engine, strict contract,
generated inventory, coverage matrix and capability descriptions used 2 at that stage.
Observation `schemaVersion` stayed 1; `contractVersion` was 2. The existing
resource/journal transport `/feature-fixture/v1` is independently versioned and
unchanged. Existing foundation operation contracts are unchanged.

There were no qualified version 1 product producers on Phone, Pico or iOS.
Version 1 host simulations are historical logic checks, not producers or
accepted product evidence. No deployed producer/acceptance migration is needed;
that registry read only 2 and rejected version 1; the current registry now
reads only 7.
The old inventory and implementation remain recoverable in Git history; the
version 2 files remain available in Git history.

The Scripts state replaces `consent` with the observed `picker` flag and adds
`companions`, the relative modules actually resolved by the active owned
engine. Inputs are ordinary picker open/cancel/accept with the two owned local
source choices; a missing source is tested through normal URL entry. A running
engine or downloaded main file without advancing entity effects and actual
relative dependency resolution cannot pass. Entity-script consent remains in
the existing `scripted-entity` foundation.

Version 2 did not activate a platform adapter. Its remaining Audio assumptions
were corrected in version 3 above. Graphics and platform Emotes still need
source-compatible contracts and full input/observer joins.

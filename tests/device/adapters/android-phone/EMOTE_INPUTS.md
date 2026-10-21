# Phone ordinary Emote input ownership, version 2

`overte_phone_emote_inputs.PhoneEmoteInputs` uses the existing candidate-bound
input session, normal Android tablet controls and original-token Qt Emote
controls. Its constructor takes the primary role's locked
[`PhoneEmoteSources`](EMOTE_SOURCES.md). It implements ordinary input for `open`,
`play`, `sit`, `override`, `cancel`, `wait-complete` and `close`. Background/resume
is explicitly unavailable here. No complete `feature.emotes.*` capability is
advertised; full observation, images, actor publication and cleanup remain open.
Native instrumentation remains uncompiled and all devices remain untested.

## Private journal and exact references

The exact header has `emoteInputsVersion:2`, `runId`, `fixtureUrl`, full original
`binding`, actual `artifactRoot` and compressed `payload`. Payload contains one
record with `historyCount`, immutable `manifests`, `pendingArchive` and `current`
(one row or null). Up to 256 ordinary inputs fit the fixture's activation bound.
Completed original rows use the `inputs` namespace of the
[immutable frame store](EMOTE_ORIGINALS.md); they do not fill the active owner
record. The current row remains inside the existing 64 KiB private-file bound.
Existing private-file
permissions, path ownership, symlink, byte limits, atomic writes and compression
digest validation apply. Each row has exactly `call`, `phase`, `before`, `intents`,
`idleReset` (a source reference or null).
Call is the existing closed v17 `feature.emotes.act` input; no expected state is
accepted. Phase is `acting`, `issuing` or `acknowledged`. `issuing` has exactly one
unfinished last intent. Acknowledgment requires complete input receipts.

Before the next call, the complete current row is archived with durable
planned/opened/saved file ownership and planned/saved manifest intent. The exact
pending archive fields are `original` and `manifest`. The original row remains
current until the immutable archive is verified. An unfinished archive blocks
the next input; a lost return cannot erase prior original receipts or deliver
the next call. Native source and input-history namespaces cannot substitute for
one another. Failed writes latch the live object closed even if a lost session
guard later returns. All complete source/input originals remain independently
validated on reconstruction.

A source reference has exactly `revision` and SHA256 `sha256`. Revision indexes
the complete original source frame in this primary role's existing transcript;
the digest is recomputed over canonical original bytes. References require the
same run/candidate/process/session/role source owner and preserve exact numeric
types. Input replay validates the referenced source originals and all retained
fixture/UI histories before adopting a journal. Source and input archives must
remain available together for final verification and digest-scoped retirement.

SDK intents have exactly `kind:"sdk"`, `controlId`, `before` and `after` (or null).
The only IDs are `tablet.open` and `tablet.close`. Both references contain fresh
original native widgets and separately observed SDK tablet visibility. The
ordinary click's return cannot supply the after-state. Ignored input fails.

Qt intents have exactly `kind:"qt"`, original `input`, original `provider`,
`barrier` (source reference or null) and `after` (new UI snapshot or null).
Input has the existing exact fields `controlId`, `action`, `sequence`, `instance`,
`generation`, `direction`, `original`. Original tokens, enabled/input-ready
controls and actual native scope select the delivered ordinary input. Every
Emote Play/toggle additionally obtains a fresh original source/Rig barrier after
token admission and before delivery; its UI is independently re-resolved against
that original token. Fixture status must still identify the same actual closed
call and extend original phase history. Other input kinds cannot borrow a Play
barrier. UI births, command counters and observation cursors remain continuous
through all original intents and SDK transitions.

## Delivery and failure behavior

The existing `TokenEmoteUI` now accepts an optional `receipt` callback. Immediately
after ordinary input, it captures a fresh original UI scope and requires exactly
the next consumed command counter. It calls `receipt({intent,after})` with copies
before returning. This additive callback leaves the existing v1 wire protocol
unchanged. It proves consumption only. Changed widget labels/highlights cannot
prove Rig playback or restoration.

The owner persists intent before every SDK/Qt delivery, then persists the actual
receipt. Lost dispatch returns, failed intent/receipt writes, ignored SDK input,
changed fixture phases, foreign UI contexts and candidate changes fail. A failed
final acknowledgment write rolls the live object back to its exact committed
state; retrying the same object cannot bypass durable responsibility. The same
rule now protects failed final source writes. `acting`/`issuing` rows cannot be
automatically retried or replaced after reconstruction. Completed duplicate
calls issue no more input and still require current owned phase/candidate guards.
The whole input has a 45-second monotonic deadline, including source acquisition,
SDK work, persistence and final guards; nested Qt bounds remain in force.

Opening a hidden tablet uses normal Android input and a fresh source read.
The actual chooser is reached through its original EMOTE button and normal
pagination/scrolling. Sit selects only the actual `Sit` control; an actual later
loaded clip determines its random variant. Cancel toggles the currently observed
active button. The common Sit discovery also resets an already idle avatar:
that no-op requires a new original source with inactive native override and an
open actual chooser reporting no active selection. It records `idleReset` and
cannot serve as a pre-input active barrier for the final early-cancel proof.
An empty highlight while the native override remains active fails. `wait-complete`
performs no synthetic restore or expected-duration sleep. Closing uses normal
Home/Close controls. Neither native avatar setters nor direct JS play/restore
commands are used for these actions.

## Whole-feature obligations

`performed:true` acknowledges handled input or that independently verified idle
reset. The complete owner
must separately join each original Play/cancel barrier to actual loaded advancing
clip frames, final poses, current original avatar pixels/challenge, each role's
own observations and independent actor publication. The counterexample with a
consumed Crying input but unchanged original Waving history fails the actual Rig
playback join. Input receipts contain no resource-absence verdict. Actual timer/
callback/input cleanup, background-resume and bounded quiet windows remain
mandatory before complete feature registration and host-journal retirement.
Device-free checks simulate explicit SDK/Qt/native boundaries and establish
adapter/test logic only.

Version 2's 256-input/1,024-source-frame storage supports the shared maximum of
169 input operations, including three times 24 ordinary Sit/reset attempts and
the remaining actions. The storage stress case retains/reconstructs all original
rows and keeps both active owners below 64 KiB. Its synthetic native stream
deliberately leaves Waving unchanged, so it establishes no successful Sit/product
behavior. Reaching any bound remains a failure, never permission to drop
originals, select a requested variant or return successful empty cleanup.

Version 1 was an unadvertised local component without a required platform
producer or device qualification. Preserve v1 inline journals for their offline
v1 reader; v2 rejects them without conversion, deletion or successful empty
adoption. Actual cleanup remains required before a fresh run.

The earlier v1 114-case affected selection passed, including original Phone factory
receipt delivery, source/Rig/root/code histories, ignored input, phase races,
failed writes on reconstructed and live objects, and completion during cancel
selection. It also verifies the documented changed-joint fraction independently
of clip position and the ordinary idle reset used by Sit discovery.
The broader 342-case Phone feature-adapter selection passed before
those final hardening cases. Documentation and version registration
also pass. No compiler, device or installation was used.

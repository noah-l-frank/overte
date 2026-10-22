# Owned Chat peer input v3

This is a fixture input component and an independent reception join. Chat stays
partial; no complete operation triple is registered. Devices have not run.

The separately qualified original Assignment Client must already own the native
[actor source](CHAT_ACTOR_FILES.md), actual downloaded script hash, original
private root/source FD, executable/PID/start and `--testScript` opt-in.
`ChatPeerInput` reuses that original `ChatActorFiles` owner and its actual kernel
FD guard. It cannot launch/adopt a process or qualify one by display name.

The separate private `chat-peer-input.v1.json` command is exactly
`{schemaVersion:1,commandId,runId,operation,...}`. Closed operations are `hold`
with bounded finite `position:{x,y,z}`, `send` with Local/Domain `channel` and
`textKey:"reply"|"hidden"`, `restore`, `release` and passive `inspect`. There are no arbitrary
message bodies, expected positions, delivery flags or observation fields.
Commands retain schema v1 and use unique run-scoped nonces and canonical JSON. Actual native code
retains all admitted IDs (bounded to 4096), pins one run and refuses any replay,
including a previously consumed command reintroduced after another command.

The E2E-only `Messages.featureChatActorInput` dispatches to the original
MessagesClient thread. It reads the original private inode and admits input once
before returning it to the original fixture script. A separate native-held
`chat-peer-input-receipt.v1.json` names both original command and result nodes,
native birth/sequence/PID/time and consumed operation. It contains no requested
position or delivery/restoration verdict. Version 2 additionally reads the actual original
ScriptableAvatar position and run-scoped actual session hash before returning
input to the script. `Agent::executeScript` installs a native `QWeakPointer`
provider, taking a temporary strong reference only for the original locked
transform read. A separate weak reference pins the actual original ScriptManager;
stopped, stopping, finished or departed scripts make the read unavailable even
if DependencyManager still retains the Avatar. Requested positions
never enter this read. `inspect` performs that original read without a fixture
mutation; it does not send chat or change position. Explicit v1 receipts remain
readable for input consumption, but cannot qualify actual Avatar position, and
an acquired version cannot downgrade in an owner. Version 3 also exports the
actual native count of Script calls into this input route. Its passive native
timer can consume only `inspect` and never advances that Script-call count.
This read remains available after Release disables the script's polling, with
fresh native Avatar position/time/sequence. `releaseConsumed` preserves native
input admission only; actual stable poll counts through a measured quiet window
must independently establish that polling stopped. Copying its bytes or rewriting an envelope inode
cannot replace the actual actor's open FD. Read-only Chat cache queries remain
on their original separate command/result paths.

The actual `domain_peer_agent.js` update callback consumes these inputs. Hold
captures its actual current Avatar position and motion phase, pauses sinusoidal
updates and assigns ordinary `Avatar.position`. Normal Send calls ordinary
`Messages.sendMessage("chat",...)` using the actual current `Avatar.position`,
display name and controlled run text. A refused position write therefore never
becomes the requested position in the message. Restore assigns the captured
original position and phase and keeps that exact point paused for independent
measurement. Release resumes the saved original motion on the next update and
stops further input polling. Script ending
also restores its locally held original before disconnecting its update and
disabling the owned avatar. Neither branch is independent restoration evidence.

Before any command publication, the host persists uncertain input ownership.
It checks the exact original command before replacement and consumes only a
fresh native-held receipt matching that original inode. Each Send tuple is
issued once, even if a different nonce is attempted later. Receipt loss blocks
new Send; one original Restore may still be attempted for recovery and retains
any uncertain prior Send. Reconstruction cannot discard that uncertainty or
restart an input owner. No method retires its journal or equates a consumed
input with an observed effect.

`ChatPeerSend` joins ordinary near Local/Domain Send to both separately queried
original `ChatSamples` roles. Both sources must be bound to the exact peer
native cache instance/process and original actor binding. New native receptions
after each independent baseline must identify that actual peer, exact controlled
channel/text and `localOnly:false`, preserving multiplicity. Both original
storage histories must independently gain the accepted row. Old matching rows,
local echoes, a consumed receipt and missing storage cannot establish delivery.
Missing reception times out without resend, retaining source/input/action
journals. Private Pico factories bind these owners to the actual installed
candidate, and process teardown refuses to hide any retained peer journal.

Eight host input cases execute real private-file ownership and the original JS
body against explicit synthetic product seams. Five reception cases use the
real source/input join with synthetic native effects. A focused real Qt5/POSIX
compiler check includes and executes the complete original `ChatActorFiles.h`
source, covering once-only admission, non-adjacent replay refusal, private
inventory rejection, original receipts and native receipt-FD closure after
release. MessagesClient dispatch, full Assignment Client/QML/application linking,
actual network transmission, OpenXR and devices remain unqualified.

`ChatPeerDistant` now composes both actual independent Chat roles, their new
native remote/local transforms and independently acquired native actor positions.
It holds the actual peer at least 30 metres from the measured primary, issues
ordinary Local hidden Send once, requires new actual remote native reception
without an accepted history/model row, then checks three seconds of advancing
fresh originals with unchanged Chat state. A forged position, accepted distant
row or missing actual reception cannot pass. Return requires the exact original
native actor point and its independently received remote transform before
Release resumes motion. A further three-second window requires stable actual
native Script-poll counters, advancing original timestamps and actual motion
observed in both the actor and remote transforms. Mutating-command admission,
Script-source freshness and failed restoration keep all journals. On a failed
flow it attempts original Restore/Release at most once without claiming recovery.
Five focused cases exercise this owner on explicit synthetic Avatar/network/
clock seams, including retained multi-channel histories and actual poll leakage.

Remaining whole-feature work includes normal lifecycle effects,
owned mixer service recovery, exact private profile
and settings-writer/file durability, reconstructed Script history and final
callback/file/cache/actor resource release. A receipt or local fixture heartbeat
cannot supply these observations. The full owner must retain journals until
those original boundaries and cleanup counterexamples are complete.

The separate `feature-chat-peer-position` native source now reads actual
MyAvatar and remote AvatarManager transforms on the original GUI thread. The
selector is the independently bound actor's native run hash of its actual UUID;
display names and requested coordinates are never selectors or observations.
The source requires the explicit E2E launch/lifecycle/results owner, valid
original transforms, at most 1024 actual avatars and a 1.5-second acquisition.
It retains its own native birth/query/sequence/PID/time and refuses replay with
a bounded 4096-query lifetime. The private Pico reader separately qualifies the
primary native self hash, exact peer hash, current candidate/process and source
freshness. Neither this source nor the actor read alone proves actual movement,
restoration or a complete distant-send rejection window.

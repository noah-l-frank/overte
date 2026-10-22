# Owned Chat peer input v1

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
`textKey:"reply"|"hidden"`, `restore` and `release`. There are no arbitrary
message bodies, expected positions, delivery flags or observation fields.
Commands use unique run-scoped nonces and canonical JSON. Actual native code
retains all admitted IDs (bounded to 128), pins one run and refuses any replay,
including a previously consumed command reintroduced after another command.

The E2E-only `Messages.featureChatActorInput` dispatches to the original
MessagesClient thread. It reads the original private inode and admits input once
before returning it to the original fixture script. A separate native-held
`chat-peer-input-receipt.v1.json` names both original command and result nodes,
native birth/sequence/PID/time and consumed operation. It contains no position,
delivery or restoration result. Copying its bytes or rewriting an envelope inode
cannot replace the actual actor's open FD. Read-only Chat cache queries remain
on their original separate command/result paths.

The actual `domain_peer_agent.js` update callback consumes these inputs. Hold
captures its actual current Avatar position and motion phase, pauses sinusoidal
updates and assigns ordinary `Avatar.position`. Normal Send calls ordinary
`Messages.sendMessage("chat",...)` using the actual current `Avatar.position`,
display name and controlled run text. A refused position write therefore never
becomes the requested position in the message. Restore assigns the captured
original position and phase, preserves that position for the restoration tick,
then resumes normal motion. Release stops further input polling. Script ending
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

Seven host input cases execute real private-file ownership and the original JS
body against explicit synthetic product seams. Five reception cases use the
real source/input join with synthetic native effects. A focused real Qt5/POSIX
compiler check includes and executes the complete original `ChatActorFiles.h`
source, covering once-only admission, non-adjacent replay refusal, private
inventory rejection, original receipts and native receipt-FD closure after
release. MessagesClient dispatch, full Assignment Client/QML/application linking,
actual network transmission, OpenXR and devices remain unqualified.

Remaining whole-feature work includes independently measured distant position
and restoration, three seconds of its actual rejected Local reception window,
normal lifecycle effects, owned mixer service recovery, exact private profile
and settings-writer/file durability, reconstructed Script history and final
callback/file/cache/actor resource release. A receipt or local fixture heartbeat
cannot supply these observations. The full owner must retain journals until
those original boundaries and cleanup counterexamples are complete.

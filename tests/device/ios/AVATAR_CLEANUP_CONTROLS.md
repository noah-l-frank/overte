# Avatar cleanup control ownership

Cleanup uses the actual current cleanup activation and a new closed local
step descriptor. It does not replay an active-phase action, substitute an act
ticket or renew an interrupted action's deadline. A step binds its concrete
root/dialog, invitation UUID/peer/phase, owned entity UUID, owned bookmark name,
controlled peer account, restored URL or scale before ordinary input.

`AvatarCleanupInputOwner` shares the original `AvatarInputOwner` event grammar,
native receipts and input validation. The base owner's act namespace and
serialized version 1 bytes remain unchanged. The cleanup facade uses its own
`iosAvatarCleanupInputOwnerVersion: 2` key and
`ios-avatar-{role}-cleanup-inputs.json` file. Its versioned call descriptor and
sequential step index allow distinct cleanup steps under the same actual
cleanup ticket. Closed input authorization is rechecked when reopening saved
event histories, including exact invitation, selected entity and replacement
operands.

Writer 2 adds the narrow `close-page` descriptor. It requires the actual
previously observed Avatar/People page root with no dialog and authorizes only
one ordinary `tablet.home`. Recovery joins the native ledger's actual page
root to that original admission, even though the shared Home control itself
has no page root. A different root cannot settle the original input. This
step keeps the tablet open: UIKit closure and genuine weak root destruction
remain separate whole cleanup originals.

The cleanup call, cleanup input owner and cleanup controls write version 2
and read versions 1 and 2. Genuine version 1 records remain readable without
rewriting and cannot contain a version 2 close-page call. The active input
owner continues to write/read version 1.

`IOSAvatarCleanupControls` retains original before/after source references,
one original 25-second operation clock and every UIKit intent. It uses the
same native input-ledger read owner and historical recipe counter as active
actions. Lost returned Qt commands and lost durable input-finish returns can
be adopted without another command or finish call. An issuing UIKit dispatch,
received-only command, changed operands, expired original step or incomplete
native read remains owned. A new step cannot replace an unfinished earlier
step. Private copies of the normal UIKit helper and the final native send
guard enforce the original deadline through slow storage and continuity reads.
The whole owner may supply its original persisted cleanup clock. Every step
then retains that exact clock; a later step or reconstruction cannot replace
it with a new start. This check precedes another native source read or input.

These controls report input completion. The whole owner must separately choose
steps from actual source ownership and verify restored model/bookmark state,
fresh bilateral relationship absence, all entity/Qt/timer/file lifetimes,
untouched post-cleanup pixels, native and host quiet and independent paired
retirement. The control component itself publishes no feature verdict.

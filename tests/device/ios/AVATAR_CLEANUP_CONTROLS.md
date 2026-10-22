# Avatar cleanup control ownership

Cleanup uses the actual current cleanup activation and a new closed local
step descriptor. It does not replay an active-phase action, substitute an act
ticket or renew an interrupted action's deadline. A step binds its concrete
root/dialog, invitation UUID/peer/phase, owned entity UUID, owned bookmark name,
controlled peer account, restored URL or scale before ordinary input.

`AvatarCleanupInputOwner` shares the original `AvatarInputOwner` event grammar,
native receipts and input validation. The base owner's act namespace and
serialized version 1 bytes remain unchanged. The cleanup facade uses its own
`iosAvatarCleanupInputOwnerVersion: 1` key and
`ios-avatar-{role}-cleanup-inputs.json` file. Its version 1 call descriptor and
sequential step index allow distinct cleanup steps under the same actual
cleanup ticket. Closed input authorization is rechecked when reopening saved
event histories, including exact invitation, selected entity and replacement
operands.

`IOSAvatarCleanupControls` retains original before/after source references,
one original 25-second operation clock and every UIKit intent. It uses the
same native input-ledger read owner and historical recipe counter as active
actions. Lost returned Qt commands and lost durable input-finish returns can
be adopted without another command or finish call. An issuing UIKit dispatch,
received-only command, changed operands, expired original step or incomplete
native read remains owned. A new step cannot replace an unfinished earlier
step. Private copies of the normal UIKit helper and the final native send
guard enforce the original deadline through slow storage and continuity reads.

These controls report input completion. The whole owner must separately choose
steps from actual source ownership and verify restored model/bookmark state,
fresh bilateral relationship absence, all entity/Qt/timer/file lifetimes,
untouched post-cleanup pixels, native and host quiet and independent paired
retirement. The control component itself publishes no feature verdict.

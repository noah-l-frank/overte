# Native pending commit owner, version 1

This internal E2E-only component owns a real prepared Scripts-field input event.
It does not implement a complete Lifecycle adapter or attest any device. The
native source is uncompiled in this local no-build phase. Host tests exercise
Python and the original probe JavaScript against synthetic native boundaries.

## Registration and source ownership

`PendingFieldCommitOwner.h` consumes a platform-provided fresh native root
reader and that platform's ordinary rendered pointer route. Registration uses
only the typed application property from `PendingFieldCommitBridge.h`; the
Test interface never constructs a fallback owner. A missing or wrongly typed
provider returns unavailable. Platform registration must require the existing
E2E launch/private-results guards, the GUI thread, actual foreground state and
actual current native UI roots. Do not replace another registered provider.

The owner walks at most 4096 actual items and 128 ancestor levels. Exactly one
visible, enabled, writable original Scripts `scriptFilter`/`filter` is required.
Its actual QQmlContext URL must equal the native PathUtils configuration for
`hifi/dialogs/TabletRunningScripts.qml`. Same-named foreign files fail. Actual
field/window/context weak identities yield a non-reused token; only owned empty,
`retry-<run>` or `Overte ä Ω 東京 <run>` text may leave this source.

## Commands and observations

The existing private command/probe path accepts action
`feature-pending-commit-owner`, schemaVersion 1. Every command has exactly
`schemaVersion,commandId,action,operation,runId,eventId`. IDs are native 32-digit
lowercase hex; iOS request IDs additionally use the existing `ios-` prefix.
Operations are `observe,focus,type,hold,attempt,release`. Every mutation also has
`ownerInstance,intentSequence`; focus/type/hold/attempt additionally require
`fieldToken,observationSequence` from an actual native issued frame no older
than five seconds. The native intent cursor must advance by exactly one and is
consumed before input. Persist the complete intent before sending once. Never
retry an uncertain mutation. Event ID is mandatory for attempt/release, optional
for observe and empty for other commands. There is no caller text, locator,
component path, expected result or arbitrary operation.

Focus uses the platform pointer route. Type uses the existing native field
helper with the closed owned retry string. Hold retains the actual original
IME event described in [the prepared-event contract](PREPARED_FIELD_COMMIT.md).
Attempt freshly walks the current original field and dispatches that exact held
event through its original context guard. Release can destroy the owned event
even when the UI roots are unavailable. It cannot erase original terminal history.

The private atomic owner-only file `feature-pending-commit-owner.json` contains
exactly `pendingCommitOwnerVersion,commandId,operation,runId,instance,sequence,
processId,canonicalComponentUrl,capturedEpochMs,lastIntentSequence,performed,
current,commit,resources`. The canonical URL is native configuration, distinct
from actual field context evidence. `performed` is only an input receipt; it is
always false for observe. `current` is `{status:none|unavailable}` or the exact
ready object `{status,token,componentUrl,text,focused,frame:[x,y,width,height]}`.
`commit` is empty or `{captureCommandId,fieldToken,observation}` containing the
original prepared-event packet. `resources` independently enumerates actual
`pendingRuns` and `archivedEvents`; unknown inventory returns unavailable.

Native bounds: one pending event globally, 32 retained immutable event records,
64 actual field identities, 256 issued observation leases, 512 unique command
nonces. At the nonce ceiling only exact owned release remains possible; its
intent cursor still prevents replay. A duplicate latest command returns its
original packet without re-execution or refreshed time; older reused nonces
fail. Prepared input expires after its original ten-second monotonic ceiling.
Records retain evidence until process teardown; archived terminal evidence is
not a pending resource. No owner reset or evidence deletion is exposed.

## Adapter obligations and failure behavior

`adapters/pending_commit_owner.py` reuses existing strict result/clock/privacy
validation. Platforms supply existing installed-source, PID, private-file and
native-clock guards around every I/O. Each exchange sends once, reads at most
51 times over less than five seconds and accepts at most 32 KiB. Original owner,
source URL, event identity, history prefix and time cannot change. A transport
with no durable intent callback is read-only. No shared full-feature capability
is advertised by this component.

Focus and typing require fresh independent actual field reads after the input.
A stale attempt additionally requires a genuinely new current token, the same
original pending event, an actual `rejected/context-retired` terminal receipt,
and fresh empty/unfocused replacement-field evidence. ACKs, expiry, release,
missing current field, arbitrary input rejection and successful stale delivery
all fail. Cleanup requires actual release plus a fresh original inventory read;
an exception or Python bookkeeping deletion cannot prove cleanup. Preserve the
original intent/event IDs for recovery after uncertain transport failures.

Ten host cases cover normal ownership/retirement/release, ignored focus/type,
missing capture, ignored/sent stale input, failed release, stale issued tokens,
read-only mutation refusal, missing/foreign replies, source/PID/URI/text/frame/
inventory faults and immutable event history. One executes the original probe
function in Node. These are test-logic checks only. Native compilation, actual
IME selection, platform foreground/pointer routes, OS/VR keyboard and complete
Lifecycle generation/world-input/position joins remain unverified or missing.

The same private writer correction puts the existing Chat and Web DOM observation
filenames in its existing atomic owner-only allowlist. No public data channel or
permissive write fallback is added.

The explicit common no-build selection passed 812 host checks with zero failures,
errors, skips or attempted compiler launches. No native source was compiled.

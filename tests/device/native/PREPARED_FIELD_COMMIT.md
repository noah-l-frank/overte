# Original native prepared field commit, version 1

`native-pending-field-commit` version 1 is an E2E-only native primitive and
strict Python receipt reader. It does **not** expose a complete normal input
transport, current page observer, full Lifecycle adapter or device acceptance.
The C++ code is uncompiled in this no-build phase; host tests execute only the
reader with synthetic native packets. No Qt event, keyboard or device ran.

## Actual native ownership

[`PreparedFieldCommit.h`](../../../libraries/ui/src/ui/PreparedFieldCommit.h)
and its implementation in
[`NativeFieldInput.cpp`](../../../libraries/ui/src/ui/NativeFieldInput.cpp)
exist only under `OVERTE_E2E_FEATURE_TESTS`. Construction also requires the actual
GUI thread and `--testScript`. The existing ordinary production helper bodies
remain byte-identical to shared commit `aa64e9f81a`; no product input, field
handler, default keyboard behavior or lifecycle policy is changed.

`prepareFocusedScriptFilterCommit` accepts only the actual focused, visible
Running Scripts `scriptFilter` field, whose original QML id is `filter` in a
local/qrc `hifi/dialogs/TabletRunningScripts.qml` context. Its actual context URL
must equal the application's original `PathUtils::qmlUrl` for that component,
so a foreign directory with the same filename/id cannot capture input. It reads actual IME
surrounding text/cursor/anchor through the existing native query. Actual text
must be `retry-<run>` and the closed commit input `Overte ä Ω 東京 <run>`. It uses
normal native Select All and independently verifies the actual selection before
creating a real `QInputMethodEvent` carrying that original commit. No text
property is assigned. The prepared object retains that exact event, weak field,
window/context/ancestor identities, original selection hashes and native times.

The owning native UI bridge must select exactly one current original control,
bind its actual source/token and installed process before calling the helper.
It must hold at most one prepared object per owned workflow, persist intent
before capture/dispatch, and retain original event identity through failures.
No UI bridge/command route for this primitive is implemented by this packet.
Do not call this factory from an unbound locator or re-create a missing event
from Python text. Native source path alone does not attest installed code.

A native precise single-shot timer releases the actual event at its original
ten-second monotonic ceiling. Observation/dispatch also enforce expiry if the
GUI timer was delayed. Time is never refreshed. Invalid native clocks make the
source unavailable while cleanup still releases actual event ownership.

`dispatch` requires the actual freshly observed current original Scripts field
and window from the native UI bridge, **not** caller-supplied pointer/token
claims or a reused old reference. An absent/foreign current source cannot create
an attempted stale receipt. A different actual Qt field/window/context or
ancestor chain rejects the original event as `context-retired` without sending
it. Lost focus and changed original selection/text have separate rejection
reasons. A still-current unchanged field can receive the exact original event
through native `sendEvent`; `sent` is recorded only after that call returns and
never means that editing or a product feature succeeded. Reentrant ownership
changes make results unavailable instead of retrying an uncertain dispatch.

`release` is idempotent, cancels the native timer and destroys the original
event. After expiry it records expired, not a fabricated timely release.
Destruction releases event/timer ownership. The actual native owner still needs
an independent inventory/read before it can claim cleanup; deleting a Python
state row or returning true cannot supply that proof.

## Closed original packet

`observation(requestId)` returns exactly these fields:

- `pendingFieldCommitVersion:1`, original native `instance`, `eventId`,
  increasing `sequence`, actual `processId` and the supplied fresh request nonce.
- Original `createdEpochMs`, current native `capturedEpochMs`, actual monotonic
  `elapsedMs`, and actual `pending` event ownership.
- `source:{componentUrl,fieldName,initialTextSha256,inputSha256,inputCodeUnits}`.
  The initial hash comes from the original actual IME query. The input hash and
  UTF-16 length describe the actual retained event's commit string; they are
  controlled-input provenance, not observed product success.
- `events`, one immutable original capture and at most one original terminal
  event. Each has `sequence,kind,reason,capturedEpochMs,elapsedMs`.

Initial event is `captured/none`. Terminal is `rejected` with
`context-retired`, `focus-lost` or `editor-changed`; `sent/none`;
`released/none`; or `expired/hold-deadline`. There is no capture relabeling,
event dropping, timer refresh or terminal re-timing. A pending event cannot
survive its ceiling. Neither a release nor an expiry supplies a stale attempt.

[`adapters/prepared_field_commit.py`](../adapters/prepared_field_commit.py)
requires a separately bound original canonical component URL and checks exact
URI equality, original native PID/clock/nonce, source/input ownership, code-unit bounds,
closed history shape/deadlines and unchanged event identity/immutable prefixes
across current reads. Obtain the canonical URL from the original installed-code/UI
binding; never copy it from an unbound prepared-event packet as its own expectation.
`OriginalCommit.retired_attempt` returns only the original
`rejected/context-retired` terminal receipt. It never constructs a generation,
text/keyboard state, `deferredInputs`, attempt count or whole feature verdict.

## Remaining native/adapter join

Add source-bound Phone, Pico and iOS native UI owner/nonce routes using their
existing guarded normal UI component. Native pointer selection of current field
must remain inside the original UI walk; expose no arbitrary object paths or
expected outcomes. The native controller must retain only one actual prepared
object, publish immutable receipts in the existing private atomic-file channel,
preserve intent on uncertain input and independently inspect actual retirement.
No producer may substitute the old field for a current UI lookup.

The complete Lifecycle observer additionally needs actual current/new page
identity and generation, original field text, actual OS/VR keyboard, effective
world input and original gesture/position history, independent publisher and
cleanup. Join the retained native receipt to the actual old and new context
source tokens before projecting shared v14 facts. The current-state UI alone,
or this receipt alone, cannot complete that join. Missing Pico Create Back/VR
keyboard remains a separate concrete prerequisite. All full triples stay absent.

Eight device-free reader cases cover original capture/rejection, missing/expired/
released/sent events, other rejection causes, foreign source/run/nonce/PID,
clock/deadline faults, replay, mutated/re-timed history and incomplete inventory.
They prove the reader only; native compilation and actual Qt callback/context
behavior remain unverified.

The explicit common host selection passed 802 checks with no compiler attempts,
failures, errors or skips. After tightening canonical source binding, all eight
changed-reader cases passed again, including a foreign local file with the same
component filename. The original production NativeFieldInput bodies were also
compared byte-for-byte with aa64e9f81a. This is source/reader verification only.

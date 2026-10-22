# Lifecycle/input source contract introduced in v14

This is shared logic and a concrete input/observer contract, not a completed
platform adapter. All three full-area adapters and device acceptance are still
missing. A default-off [native retained-event helper and reader](../native/PREPARED_FIELD_COMMIT.md)
now exist alongside the [native owner/private transport](../native/PENDING_COMMIT_OWNER.md).
Platform registration and the complete pending-input/context join remain unresolved
alongside some actual Back/keyboard routes. The C++ is
uncompiled; no compiler, installation or device is run here.

## Actual pages and normal input

Start with the owned tablet/editor closed, no held input, grounded original
position and no retained pending input. Preserve unowned settings/state.
`open-editor` navigates normally from Tablet Home to the actual app and focuses
its actual field through normal pointer input. Independently observe an empty
new field before typing. Bind these exact reviewed sources/controls:

| Editor | Original field and purpose |
| --- | --- |
| Create | `scripts/system/create/qml/NativeCreate.qml`, `NativeCreateText`, the New Text initial-text field; do not create an entity |
| Chat | `scripts/communityScripts/armored-chat/armored_chat.qml`, `chatMessageInput`; do not send the draft |
| Scripts | `interface/resources/qml/hifi/dialogs/TabletRunningScripts.qml`, `scriptFilter`; do not open a script-load dialog or run a script |

Type the closed input strings with the actual native IME/controller-keyboard
route. NativeFieldInput already guards the actual focused, visible, enabled
editor/window and queries its actual surrounding text. No property assignment,
direct QML handler, generated observed text or private mutation API is input.
The existing original-token component recipes may supply supported normal
controls but do not yet provide this whole workflow.

Every app owns its own draft: Create receives `unicode`, Chat receives `reply`,
Scripts receives `retry`. Do not carry Create's text into another page. Normal
Back from the bound Create page must leave that page, release its actual focus
and keyboard and show no owned editor. On Phone, `closePhoneDialog` routes to
the tablet's normal semantic navigation then hides the IME; it does not promise
a keyboard-only first Back. The reviewed `WindowRoot.returnToPreviousSemanticScreen`
can go straight to Home. Other pages can have subordinate Back handlers, so
bind the actual Create source before choosing this recipe.

Phone may use actual Android Back. iOS uses the actual normal tablet Back
control, with its actual current semantic source/history. Pico's reviewed
3D `TabletRoot` uses the original `pico-tablet-x-back` mapping in
`scripts/system/tablet-ui/tabletUI.js`: the Pico-enabled left controller X
(`Controller.Standard.LeftPrimaryThumb`) sends a shown app page to Home and
closes the shown tablet when already on Home. The Pico default script enables
its existing `deferTabletCreationUntilOpen` condition. The original OpenXR
`left_primary_click` action and existing left/primary controller-button profile
reach that same normal control. The [bounded Pico X owner](../adapters/pico4/LIFECYCLE_BACK.md)
retains its exact one-send stream and independently observes Home, original
Qt editor lifetimes and actual VR keyboard quiet. This establishes a concrete
normal Back route; the complete sixteen-step Pico adapter is still missing.
Do not call Home or `returnToPreviousApp` directly or treat an input ACK as
observed Back, context retirement, released keyboard or completed cleanup.

Chat background/resume retains its own typed draft. The original `chat.hidden`
handler releases text focus and `keyboardRaised` without clearing text. Require
fresh actual native lifecycle advancement and actual OS/VR keyboard absence;
QML keyboardRaised/requested state alone is insufficient. Preserve app identity
under the existing background profile and source-bound continuity checks.

## Actual context generations and pending stale input

`generation` describes the current actual owned page/editor identity. Zero means
no active owned editor. Assign 1, 2 and 3 only on observing the original newly
created Create, Chat and Scripts Qt page/control identities, respectively.
Record original creation/source IDs, actual loader identity and nonreused weak
QObject identity; do not increment on a request/acknowledgment. An inactive old
object must not borrow the current page's alias. Observe source destruction or
actual retirement and current focus/window independently.

After Scripts actually contains `retry`, `hold-editor-input(unicode)` retains
exactly one original native commit dispatch for that actual Scripts field and
its original window/source/generation, before delivery. A source-bound native
pending receipt must retain original event ID, input bytes/hash, original cause,
time, weak field/window identities and generation 3. It must describe an actual
captured input, not a synthetic command saved in a Python dictionary. Limit the
test-only hold to one commit, 4096 UTF-16 code units and ten seconds; expiry
releases ownership without dispatch and cannot satisfy the stale-attempt test.
No real product input path or production watchdog is changed by this contract.

`replace-context` normally closes the old Scripts page, returns through Home
and opens a genuinely new Scripts page without focusing its filter. Verify the
actual original generation-3 retirement and different current Qt page/control
identity before assigning generation 4. The new actual filter is empty, with no
text focus or keyboard. Keep the original pending old-context commit alive in
the E2E holder; do not rebind its field/window/source or copy it into the new page.

`deliver-stale-input` has no new text input. Attempt the original retained native
dispatch exactly once through its original current-context/weak-object guard.
The actual guard must reject its retired generation before sending any IME/key
event to a replacement field/window. Preserve an original attempt/rejection
receipt with the same original event ID/hash/source and actual cause/time.
Release the holder after the actual attempt, then require an empty new field
and no keyboard/focus/held input for three seconds. Merely dropping the event,
sending arbitrary stale bytes or acknowledging an ignored call cannot pass.

`close-editor` normally leaves the generation-4 Scripts page and closes the
owned tablet. Current editor/text/generation become none/empty/zero. This does
not rewind the original creation-ID history. Do not restart the app to fabricate
a context replacement: process/lifecycle continuity remains unchanged here.

## World input, attempt counters and stationary release

The first `world-input(forward)` must actually dispatch one original normal
platform gesture while Create owns focus. `worldAttempts` advances to 1, but
actual effective avatar held input and displacement remain empty/zero. Without
the original native event receipt, a quiet avatar would be a vacuous negative.

After all editors close, dispatch a new actual held forward gesture. Observe
`worldAttempts` 2, effective avatar input `forward`, and original actual world
displacement 0.3..3 metres. `heldInputs` measures current effective avatar drive
input through the original native controller/avatar path; it is not a requested
key name, an injection lease or an OS-down acknowledgment. Pair current actual
native input with grounded position and an independent observer/peer. The
controller/IME route and actual world movement must agree. `positionDelta` is
the original current grounded feet position minus the independently frozen
initial feet position, in the same unchanged world coordinate frame. Its three
finite x/y/z components are measured in metres; its norm must agree with
worldDisplacement within 0.025 m. Neither value is the requested movement. Keep existing input
watchdogs, TTLs and bounded gesture leases; missing timing/continuity support
makes the adapter unavailable instead of authorizing a guard change.

`release-input` actually neutralizes that original held gesture. Empty effective
held input alone is insufficient: require three seconds of original three-dimensional position
stability within 0.025 m of the current stable-window anchor. Continued small
motion within the broad 0.3..3 range resets the window and cannot pass. Compare
all three original position components: movement along a constant-distance arc
cannot borrow an unchanged scalar displacement as proof of being stationary. Restore
the actual original grounded position using the existing normal controlled
navigation/scene route, retaining neutral input and independently observed zero
relative displacement. Original changed world pixels supplement native/peer
position; an input acknowledgment never proves motion or release.

`worldAttempts` counts original dispatched test world gestures (one per original
gesture ID, not keepalives). `staleAttempts` counts original held callback guard
attempts; it advances to 1 only after the original stale dispatch really reaches
its guard. Counters are measured from immutable original histories scoped by
the owned initial source barrier. They cannot count commands, desired outcomes,
field edits or unrelated global events. `deferredInputs` is the actual holder
inventory, zero or one. All eleven fields—editor, text, keyboard, focused,
heldInputs, worldDisplacement, positionDelta, generation, deferredInputs, worldAttempts and
staleAttempts—require fresh independent current observations.

## Deadlines, failure and cleanup

Use existing twenty-second observation deadlines, fresh run/ticket barriers,
native clock/PID/source continuity and three-second negative/cleanup windows.
The hold/replace/attempt sequence must finish inside the native holder ceiling;
do not silently refresh its original time. Native keyboard identity/visibility,
original input attempts, actual current page/source and real held callback
receipt are mandatory capabilities, never expected values relabeled as reads.

Cleanup twice: neutralize only the owned current gesture, release the original
pending holder including after partial failure, close owned pages/dialogs,
restore the original position and verify no active owned input/context/file
leases. Inactive current generation is zero. Preserve original immutable
world/stale attempt counters at their last observed values during cleanup;
the engine rejects regression instead of demanding an impossible global reset.
Their retired history is private evidence, not an active input lease. Check
restored state and empty resource inventory independently for three seconds.
Unreleased callbacks, old contexts, moving release, reset counters and partial
cleanup are failures. Original native histories may not be erased to pass.

The final v14 packet passes 794 explicit common host checks, including three
original QML handler checks and counterexamples for inherited drafts, wrong
Back outcome, missing original held/attempted events, stale-context adoption,
unreleased commits, moving release (including constant-distance arcs), reset
histories and incomplete cleanup. Native compiler checks remained excluded;
no compiler, installation or physical run occurred.

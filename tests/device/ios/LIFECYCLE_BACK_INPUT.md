# Ordinary iOS semantic Back input

The dedicated iOS E2E input route now recognizes the existing rendered
`nav.back` button from `TabletNavigation.qml`. It uses the ordinary Qt pointer
press/release path. It does not call `returnToPreviousSemanticScreen`, select a
destination or substitute Home. Existing QML behavior decides whether a page
handler consumes Back or the previous semantic screen is loaded.

The passive native source requires the GUI thread, dedicated iOS E2E flags,
actual test-script launch, native-configured exact navigation/WindowRoot QML
URLs, the actual common window and screen-space root. Its root UUID is created
only inside that guarded observer. It hashes the actual semantic screen ID and
bounded original source-history array; these hashes bind input tokens without
exporting arbitrary page URLs. A pending Back target refuses another press.
The normal source-token path rechecks the current native metadata immediately
before pointer delivery. Hidden, disabled, foreign, changed or replaced roots
cannot use the old token. No product/QML navigation handler is changed.

`NativeInput.tablet_back_input` requires a complete original control reference
and a durable intent callback. It reobserves the same source, process, control,
root/history hashes and unconsumed input sequence, writes the exact command
intent before HTTP delivery, and sends once. A lost result is uncertain input;
no resend or successful navigation is inferred. The caller must retain that
intent and recover through independent current editor/page observations.
The returned `performed` field proves delivery only. It supplies no editor,
keyboard, world-displacement, stale-callback or cleanup verdict.

`tabletBackControlsVersion:1` and `tabletBackControlVersion:1` are optional
closed source extensions. Older observation packets stay readable. A Back
control requires both extensions; a legacy packet cannot claim this new route.
The shared input command/result schemas and public capability list are unchanged.

The host entry points are
`ios.self_tests.test_ios_tablet_back_controls.TabletBackControlsTests` and
`self_tests.test_lifecycle_source_semantics.LifecycleSourceSemantics`.
The new transport cases exercise real HTTP/AFC codecs and private intent files
over declared native/process boundaries. The existing Node cases execute the
original QML semantic Back and Chat-hidden functions. Neither executes Qt,
UIKit or native compilation. Native root/context resolution and actual rendered
Back delivery remain uncompiled and device-untested.

The coordinated no-build selection passes 20 cases in 0.596 seconds: six new
Back transport/ownership cases, eight existing native-input cases, three
original QML semantics cases and three canonical Emote Stop/binding regressions.
Ignored/lost input, refused intent, replaced root/page/history and malformed
source packets retain the closed behavior. These are host results only.

Lifecycle/input remains partial. The next complete owner must retain distinct
Create/Chat/Script editor generations, actual OS keyboard/focus evidence, held
input/stale-commit originals, independent Actor/position/image effects and
paired quiet cleanup. This input prerequisite enables no complete capability.

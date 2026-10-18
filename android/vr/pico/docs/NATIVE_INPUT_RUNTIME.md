# Native input/runtime changes — revision 09

## Controlled normal tablet navigation input

The E2E-only `PicoE2eNavigationUi` resolver observes the actual system tablet
root/window. It resolves visible unique address/history controls, the ordinary
GOTO TabletButton and actual page indicators. Native pointer input uses the
existing `OffscreenQmlSurface` hover/press/release route. Text replacement and
Return use the shared, focus-guarded `NativeFieldInput` implementation. No
AddressManager call, direct QML slot invocation or expected navigation state is
available to the resolver.

The fixed active private probe gates its installation alongside the existing
tablet bridge. Separate `navigation-ui-observation.json`,
`navigation-ui-command.json` and `navigation-ui-status.json` files retain the
existing settings/tablet contract unchanged. Commands bind the process-local
bridge, current root/window generation, live control token, increasing sequence
and a native observation at most five seconds old. An admitted input sequence is
consumed before delivery; uncertain input is never replayed. Duplicate controls,
hidden/clipped controls, stale tokens and foreign-thread access fail closed.
Text and feature verdicts are absent from delivery status.

`pico-tablet-e2e-adapter-test.py` now compiles the actual resolver and shared field
implementation, then runs native Qt pointer/key/IME counterfactuals in an isolated
network namespace. The `OVERTE_NATIVE_QT_MAJOR=5` and `6` variants are distinct
host executions. Qt 5 also executes the unchanged in-tree VR hover/pointer
methods, actual PointerEvent header/constructors and bridge pointer function on
a real render-control window. Both variants retain the actual GOTO activation
and MouseArea handlers with their own QML component scope. The full surface's
root/window/pause and tablet audio providers are controlled test boundaries.
Qt 6 exercises the shared resolver with native Qt mouse primitives. A separate
GLM SDK include root can be selected with `OVERTE_TEST_GLM_INCLUDE`; application
headers and source always come from this composed checkout. These checks do not
build the full Pico application or prove OpenXR/device behavior.
The original candidate-bound Pico adapter now connects normal Go To/history
under the explicit configuration documented in
[`NORMAL_NAVIGATION.md`](../../../../tests/device/adapters/pico4/NORMAL_NAVIGATION.md).
Its owning tablet check also executes the original installed-candidate tests,
including native input counterfactuals. The generic unbound ADB adapter does not
advertise these operations. Host input/protocol qualification still does not
establish a native application build or physical-device acceptance.

## Earlier runtime integration

PI-003/005/007 production callers now apply these local rules:

- PicoInterfaceActivity forwards alphabetic external keyboard events to Qt only
  while focused and only for keyboard sources without gamepad/joystick source
  flags. Controller-origin Android keys remain consumed; OpenXR owns controllers.
- Android window focus loss cancels all registered WebView touch gestures,
  clears fractional scrolling and releases WebView focus.
- AndroidAudioInput checks microphone permission before creating a recorder and
  both before and after each blocking read. Revocation prevents that read from
  reaching JNI and enters existing cleanup. Recorder identity is volatile, and
  capture buffers are zeroed on loop exit.

Actual callers are under apps/picoInterface/src/main/java/org/overte/pico.
These entry files are authorized by revision 09 to connect the backlog-owned
input, lifecycle and audio nodes; no Shared Qt/QML or runtime file was changed.

Focused tests execute the keyboard decision, compile audio against API 26 and
all production Pico Java callers against SDK 36, and validate the native/JNI
delivery boundary. Compile-only Qt/resource stubs live exclusively under tests.
They do not prove a Qt runtime, device input, microphone route, OpenXR focus
transition or worn-headset behavior. Shared SH-003/005/006 binding remains pending.

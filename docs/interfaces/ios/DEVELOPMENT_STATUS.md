# iOS development status

## Current product boundary

The integrated Qt/Overte client is the active product path. The maintainer's
[iPad personal-alpha milestone](https://github.com/noah-l-frank/overte/milestone/3)
was completed on October 10, 2026 with eleven closed acceptance issues. That
record does not qualify an arbitrary newer IPA or every iPhone/iPad model.

Current work is [IOS-P2 cross-client feature parity](https://github.com/noah-l-frank/overte/milestone/6).
Its open acceptance issues and the
[shared feature contract](https://github.com/noah-l-frank/overte/blob/main/docs/interfaces/FEATURE_PARITY.md)
define the remaining scope. Use the
[build qualification guide](../../IOS_BUILD_QUALIFICATION.md) to inspect actual
build results and bind an IPA to its source, producing run, and installation.
A successful host test or a historical milestone alone does not establish that
binding for today's installed app.

## Bootstrap and historical preparation

The separate UIKit/Metal bootstrap still tests bundle, lifecycle, deep-link,
place-resolution, simulator, and device-SDK contracts. It is a diagnostic target,
not the complete networked Interface. The early
[port preparation inventory](../../ios/PORT_STATUS.md) and
[preparation iteration plan](../../ios/ITERATION_PLAN.md) record that earlier
stage; their Qt, V8, MoltenVK, and recipe blocker lists are not a current
qualification dashboard.

## Physical-device work

The maintainer's hardware tests use the private Proxmox Jenkins laboratory.
The workstation device lab is retired. Separately authorized manual IPA signing
and installation remains a distinct path; it is not device acceptance. This
personal infrastructure is not required for local host-contract tests. Current
artifacts still need their selected rendering, audio, microphone, touch,
lifecycle, and other acceptance journeys. Broad hardware coverage and App Store
submission remain separate from the personal alpha.

## Touch acceptance paired with the next rendering build

At the device tester's explicit request, the physical rendering build contains
the shared fixes integrated through `main` from the former
`fix/universal-touch-ui-tablet-qml` branch rather than duplicating them as an
`apple-ios` implementation:

- tablet startup and direct touch interaction: `55da2d017e`, `2361d3a9b5`;
- shared TextField context fix: `54d6103edc`.

Validate on both iPhone and iPad that tablet icons appear, short taps work,
swipes do not trigger icons, and Goto/Login/other text fields open the iOS
system keyboard on a short tap. Also validate focus, keyboard geometry, safe
areas, and resize behavior.

## Physical-device iteration controls

The iOS client enables the expanded statistics overlay by default so render
rate, present rate, position, network and scene counters are visible during
device acceptance. Unlike the reduced Android FPS badge, the iOS selector uses
an iPad-sized three-column diagnostic panel.

`Documents/overte-ios-render-diagnostics.json` selects Web/QML upload
diagnostics without rebuilding. Supported fields are:

```json
{
  "mode": "normal",
  "format": "rgba",
  "flipVertical": true,
  "forceOpaque": false,
  "captureFirstFrame": true,
  "captureFrameOrdinals": [1, 2, 4, 8],
  "captureLatestFrameSequence": 1,
  "captureSourceContains": "Wizard.qml",
  "screenQmlFlipVertical": true,
  "screenQmlCaptureFrameOrdinals": [1, 4, 8],
  "screenQmlCaptureLatestFrameSequence": 1,
  "qmlSoftwareWarmupFrames": 8,
  "qmlSoftwareDiagnosticContinuousFps": 0,
  "statsOverlay": true,
  "statsOverlayExpanded": true,
  "touchUiAutoOpenTablet": false,
  "virtualPadForceVisible": true,
  "virtualPadScalePercent": 100,
  "touchJumpMinimumPulseMs": 120,
  "touchInputTraceLimit": 64,
  "offscreenKeyTraceLimit": 64,
  "locomotionTraceIntervalMs": 250,
  "cameraMode": "third-person"
}
```

`mode` is `normal` or `test-pattern`. `format` is `rgba`, `srgb`, `bgra`, or
`rgba-from-bgra`. The first-frame log includes visible/opaque/non-black pixel
counts and corner/center RGBA samples. When capture is enabled, the exact image
sent to Vulkan is written to `Documents/Overte-iOS-QML-FirstFrame-*.png` for
AFC retrieval. Later ordinals use `Overte-iOS-QML-Frame-*.png`. Increment
`captureLatestFrameSequence` to request another current frame. Set
`qmlSoftwareDiagnosticContinuousFps` from 1 through 15 when otherwise static
QML must keep producing frames for a live investigation, then return it to 0.
The JSON is checked for updates once per second; these controls do not require
an app restart.

Screen-space QML (statistics, mobile action bar, dialogs, and tablet) has its
own `OVERTE_IOS_SCREEN_QML_FRAME_GATE` marker and capture ordinals. The iOS
Vulkan HUD also draws the virtual movement pad and jump/handshake buttons;
`virtualPadForceVisible` provides a visual diagnostic fallback before scripts
finish, while `virtualPadScalePercent` accepts 50 through 200. `cameraMode` is
`third-person` (the iOS default), `first-person`, or `persisted`.
`touchInputTraceLimit` bounds classification markers for move, view and button
touches; set it to 0 after input acceptance. `touchJumpMinimumPulseMs` keeps a
short jump tap visible to at least one mapper update even when the first iOS
frame after release exceeds the configured pulse; `stage=jump-pulse-exposed`
records that guaranteed sample. `offscreenKeyTraceLimit`
bounds hardware-keyboard routing markers without logging typed text, and
`locomotionTraceIntervalMs` controls the active locomotion-state marker cadence.
Set either trace value to 0 to disable its corresponding diagnostic.

Set `touchUiAutoOpenTablet` for a launch that must expose the screen-space
tablet without a manual tap. This exercises the same shared tablet presenter as
the selected phone scripts, but uses live UIKit safe-area, surface, density and
keyboard metrics from the existing `+ios/TouchUiProfile.qml` adapter. The
`OVERTE_IOS_TOUCH_UI_GATE` markers report metrics, resize bounds, registered
buttons and final visibility. `statsOverlay` and `statsOverlayExpanded` permit
clean comparison screenshots without another IPA.

On iOS, the offscreen HUD, tablet window and incoming Qt touch positions all use
the same safe-content-local coordinate space. UIKit safe-area insets are removed
exactly once when the render target is sized; controls and QML windows must not
subtract the top or bottom inset a second time. Hardware-keyboard events are
routed to the active offscreen QML focus item, while the native input assistant
is suppressed without disabling text input.

Reviewed QML can also be replaced without rebuilding. Create
`Documents/OverteQmlOverrides/.enabled` and mirror the QRC-relative file path
below that directory, for example
`Documents/OverteQmlOverrides/serverless/Scripts/Wizard.qml`. Only regular,
non-symlink files canonically contained by that root are accepted, and every
active override is recorded by `OVERTE_IOS_QML_OVERRIDE_GATE`. If an override
uses relative imports, mirror those dependencies as well. Remove `.enabled` to
return atomically to bundled QML.

The iPad orientation decision was made on 2026-10-07: the Full Client must stay
landscape even when the device is held upright. The iPad bundle and UIKit policy
implement this requirement; iPhone policy remains unchanged. Physical acceptance
must verify the lock at startup, during tablet/keyboard use and after background
return. See [the touch matrix](TOUCH_UI.md). Shared Touch UI contract changes
originate from main; native iOS orientation adaptation remains on `apple-ios`.

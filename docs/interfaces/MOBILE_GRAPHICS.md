# Mobile world appearance controls

Android Phone exposes native Graphics settings for local lights, haze, custom
material shaders and mirrors. It also allows render resolution from 50% to 70%
while retaining the existing 30 FPS target. Choices persist across restarts.
The Android product profile enables this page only after the shared controller
and Settings message routing have been integrated.

The startup list is shared with iOS. The controller therefore requires both the
immutable Phone startup flag and the native platform's Android OS identity
before touching renderer state. Only the first-party Settings screen can submit
changes. Other applications, malformed keys and values outside the supported
budget have no effect. Enabling lights restores the full clustering grid before
admitting light content; disabling them stops lights before reducing the grid.

`GraphicsSettingsBase.qml` retains the generic Graphics page. The unselected
`GraphicsSettings.qml` remains a compatibility entry, and iOS must select a thin
`+ios/GraphicsSettings.qml` wrapper around the generic body when the shared
Phone selector is propagated. This preserves the existing iOS page.

Run the shared behavior checks from the repository root:

```bash
node --test tests/javascript/test/phone-graphics.production.test.js
node --test tests/javascript/test/default-scripts.production.test.js
python3 tests/device/contracts/tablet/test_tablet_qml.py
python3 tests/run-project-tests.py --profile quick --timeout 240
git diff --check
```

The Phone branch additionally owns real Qt 5 pointer, narrow-layout and font
scale tests. Host checks establish message routing and UI behavior; physical
acceptance still requires each effect to be visible in the common reference
world, restart persistence and performance observations on the exact APK.

The generic Graphics page uses the native `Render.deferredRenderingAvailable`
capability. Android's renderer registers a forward task directly, so that page
keeps haze available while hiding deferred-rendering, bloom and deferred AA
controls. It does not offer a switch that only changes a saved enum. iOS and
desktop retain their deferred controls. Lighting choices reach both camera
views and every registered nested mirror view in both render branches; deferred
AA reaches the jobs inside each deferred task. The existing three-mirror,
three-level budget remains unchanged.

Run the focused production traversal and complete-page tests with an explicit
Qt major (configure matching pkg-config/runtime paths for an extracted SDK):

```bash
OVERTE_NATIVE_QT_MAJOR=5 python3 tests/device/contracts/graphics/test_render_configuration_traversal.py
OVERTE_NATIVE_QT_MAJOR=5 python3 tests/device/contracts/graphics/test_graphics_settings_qml.py
OVERTE_NATIVE_QT_MAJOR=6 python3 tests/device/contracts/graphics/test_render_configuration_traversal.py
OVERTE_NATIVE_QT_MAJOR=6 python3 tests/device/contracts/graphics/test_graphics_settings_qml.py
```

The traversal fixture derives registered paths and recursion limits from native
source, executes production traversal bodies and checks replacement
configurations. The page test uses real Qt Quick controls and pointer input;
native renderer/setting endpoints and the scene/GPU remain explicit boundaries.
Neither test establishes rendered effects or device persistence.

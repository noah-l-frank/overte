# Normal immediate Graphics controls, version 1

This internal input component implements no complete `feature.graphics.*`
operation. It proves no rendered effect, framebuffer acquisition, pass execution,
persistence, application restart or device acceptance. Native C++ remains
uncompiled. Its thirteen host boundary checks validate the ordinary-input recipe.

The read-only `NormalGraphicsControls.h` resolver recognizes the actual existing
`settings.graphics` Flickable and original QQuickSwitch/QQuickSlider controls.
It distinguishes the ready/values Phone page from the actual generic preset-
state page. It recognizes only the immediate viewport-resolution slider, Haze
and Mirrors; Pico's separate runtime-eye-resolution/restart selector is not a
substitute. The generic wrapper's child Switch/Slider is the actual input target,
not its caption or enclosing label. No product UI or handler is added.

The owner supplies `GraphicsUiContext` using actual original Render resolution,
haze and mirror getters on the GUI owner under the explicit feature test launch.
No request accepts those measurements as results. The existing `NormalControlUi`
core now has a Graphics surface using the same actual QObject/source tokens,
process/root/window generations, bounded observed-input lease and consume-before-
delivery command cursor as the existing Script/Audio surfaces. Their existing
wire contracts stay unchanged. Missing context makes Graphics unready.

Graphics wire version is `graphicsControlsVersion:1`. Every row has original
`enabled`, separate `inputReady`, and `viewport` exactly visible/above/below/
outside from actual scene geometry and clipping. Offscreen controls retain
read-only metadata/tokens so scrolling uses their measured direction. Hidden or
foreign pages are not searched. `graphics.page` is a noninteractive marker with
actual phone-immediate-v1/generic-immediate-v1 profile. No full-size native button
may cover the page. The scrollbar and slider must never be activated as buttons.

The closed metadata fields/types are defined by `token_graphics_ui`. Resolution
rows have actual Qt value/range/step plus separate original nativeValue; toggle
rows have actual checked/nativeChecked. Readiness requires a ready current page
and coherent original Qt/native setting, including an attainable slider grid.
Scrollbar position/size are original finite values. Source tokens retire on
actual value/check/readiness/profile/viewport/scroll and slider geometry changes.

Inputs use normal pointer presses/releases, with original target token preserved
through native re-resolution. `set-value` accepts a finite target on that actual
slider's range/grid and presses the actual track computed from its original
padding, handle, available width and layout direction. No Slider.value assignment,
QML moved/toggled/handler invocation, Render setter or script-message shortcut is
exposed. `scroll` uses only up/down and the real scrollbar groove beside its
original thumb; wheel events over gain/settings sliders are forbidden. The
native core verifies the actual scene hit before either press. No hidden or
covered control can authorize delivery.

`TokenGraphicsUI` pins native instance/generation and actual page profile. Its
IO owner must independently verify fresh original requests, process, source
cursor and clock at the existing platform boundary. Before every normal input,
the required owner callback validates and durably commits intent. IO must compare
the recipe's original token to the current resolved control, never adopt a newer
token. ACKs are delivery only. Each result wait is bounded to 10 seconds/101
reads; scroll has at most eight measured advances, each requiring real position
change. Absent/outside controls cannot cause guessed scrolling. Invalid/off-grid
resolution is rejected before any scroll. Missing results never replay input.

The owning full adapter must independently freeze original preferences and
resource binding before the first modification, verify they are restorable via
ordinary controls, track owned settings/page/scroll and unresolved inputs, then
restore/independently observe the actual originals across all failure/restart
paths. The common version 4 journey freezes its own independent baseline and
checks close/background/restart durability. Native setting readback cannot fill
its renderScale/hazePass/mirrorPass or image fields. Actual completed frame/pass
sources, controlled Graphics subject acquisition, actor/journal joins and full
ownership cleanup remain separate mandatory requirements.

At this packet the shared resolver/core/recipe is present but platform Graphics
transports are not yet connected. No full feature capability is advertised; the
canonical iOS installed-code gate continues to block private components.

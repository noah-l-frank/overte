# Original VR Graphics UI observation

`pico-graphics-ui-observation` v1 is an internal passive source. The existing
candidate/OpenXR/PID-start guarded factory sends only a fresh observe nonce to
`graphics-ui-command.json`; original `graphics-ui.json` bytes are atomic and
owner-only. Input actions are refused by both the Python transport and native
producer. No complete `feature.graphics.*` capability is enabled.

The producer reads the real VR TabletRoot/offscreen window, original generic
immediate Graphics controls and native Render values, physical tablet visibility,
actual editor focus and native 3D keyboard state. The separate Pico restart-only
swapchain-resolution control is not part of this source's immediate-control
profile. Phone profiles cannot satisfy this reader.

The existing weak login/menu tracker is factored into `FeatureUiInventory`, with
its original Login default and compatibility alias preserved. Graphics selects
its actual generic root and original scrollbar timer. The timer is found through
its own QML context ID and original QObject ancestry, including inherited QML
contexts; missing/ambiguous/foreign-thread timers make observation unavailable.
The original Menu timer/item source remains shared. Roots never gain a strong
owner through observation. Hidden or detached roots persist as resources until
actual QObject deletion, with bounded original retirement history.

The Graphics registry also observes the existing normal native control read
before a possible close/replacement. It shares the same weak inventory as the
passive publisher, so an ordinary input-side snapshot cannot be forgotten merely
because no independent publisher has polled yet. QML component/status callback
lifetimes are observed separately through the existing original component
inventory, including finished-but-retained components.

Physical tablet hiding does not prove page destruction. The source retains that
separation, and its resource reducer continues reporting an original hidden
Graphics root, retained menu, QML load, raised keyboard or actual editor focus.
Durable original UI history pins birth/generation/cursors/roots for a later fresh
query; historical data never satisfies a current read. Original invalid or
missing sources do not become empty inventories. Final native time and guard
checks remain inside the original freshness/processing bounds.

A complete input owner must use the normal observed Home ray before closing its
owned Settings page/tablet, then independently require root/component retirement
and a quiet window. Go To uses a different original Address dialog and
`request-service.js` HTTP callback path: this Graphics inventory does not prove
those callbacks retired. The full scene/navigation owner still needs that
separate original lifetime source, as well as actual HMD/framework entity
ownership and exact scene/avatar restoration. Neither disappearance nor an input
ACK supplies those facts.

Host seams verify control/profile/cursor refusal, hidden roots, retained
components/menu callbacks, focus/keyboard resources, one-send/no-input transport,
private candidate guards and historical continuity. Authentication host regressions
remain passing after the shared weak-tracker extraction. Native C++/QML code has
not been compiled, and no target/device was used.

## Original composition v2

The passive source now emits v2 with an original `composition` observation.
Both v1 and v2 readers remain explicit. The separately selected
[stereo surface profile](../../native/STEREO_GRAPHICS_SURFACES.md) requires v2
on both sides of the original capture and independently checks opacity, coverage
and registered native screen/frame identity. An incomplete property observation
still permits resource inventory but cannot admit a shown tablet for this new
profile. Native source is uncompiled and devices are untested.

# Original Pico world-surface evidence v2

The explicit image policy is `{"source":"world-render-target","profile":
"pico-stereo-graphics-v2"}`. The common runner selects the separately pinned
[`pico-stereo-cues-v1` fixture](../feature_journeys/GRAPHICS_SURFACE_CUES.md)
before any target preparation. The image policy and reader credential are never
sent to a target adapter. Legacy image policy/metadata v1 remains supported and
continues to refuse a shown tablet.

## Original pixels and state

[`stereo_graphics_surfaces.py`](../adapters/stereo_graphics_surfaces.py) reads the
unchanged original world-render v4 PNG, exact current seven-entity scene and
actually used GPU cameras. The far Haze code is projected directly. The reflected
Web plane is reflected about the actual mirror plane and projected with the
original root Mirror camera; that camera is not the reflected target camera.
Both eyes independently decode the complete surface magic, nonce and CRC32.
Every distinct actual camera must pass. Three-pixel original cell spacing and
multiple central original pixels are required; no crop, resize, eye copy or
reconstructed pixel is admitted. Near-marker overlap, weak contrast, mixed
cells, stale/foreign identities and wrong original geometry remain unavailable.

Each row is calibrated from its actual dark and light cells before decoding.
Color statistics are computed from independently classified actual light cells.
Haze changes require the native setting/pass direction and more than ten units
of blue-dominance change in all eight fixed light calibration cells in each eye.
Mirror-on requires the current reflected code in each eye; mirror-off refuses
any valid reflected code, including stale/foreign ones. Native setting or input
acknowledgment alone never establishes an effect. Original HTTP scene/HTML/PNG
socket receipts and exact resource hashes must precede their corresponding
original subject/frame observations.

## Original UI prerequisite

Pico passive UI observation v2 adds `composition` from the actual HMD screen
entity and actual TabletRoot QQuickRectangle. It records screen/frame identity,
visible/alpha/background/pulse properties, the weak root birth, original RGBA,
radius, mapped quadrilateral, viewport and ancestor visibility/opacity/layer/
mask/clipping properties. Missing readable properties produce an explicit
incomplete observation. No product input or property setter is used.

The verifier admits a shown tablet only with its exact present native screen
and frame registrations, alpha one, no alpha pulse, an opaque square-corner
background covering the complete offscreen viewport, and visible opaque
ancestors without layers/masks or partial clipping. Rotated bounding boxes do
not substitute for full quadrilateral coverage. These are original composition
prerequisites, not GPU visibility claims; the independent codes in both original
eyes establish which world surfaces remained visible. Raised keyboards are
refused. The actual UI is observed on both sides of the capture, with distinct
increasing source cursors and identical admitted composition/control state.
Unknown or transparent composition cannot be bypassed with a valid near-marker.

## Durable producer and compatibility

Metadata v2 adds the original `graphicsAfter` acquisition. The source reader
retains explicit v1/v2 parsers and refuses downgrade after acquiring/restoring
v2. Sampler v5 retains a v4 legacy journal reader, restores the final UI cursor,
keeps every original file identity and independently retires all native image
buffers, callbacks and receipt files before publication. Original-file v2 reads
v1 records and metadata v1/v2. Historical reduction accepts no fabricated
current clock; the live sampler separately proves its actual final freshness
and candidate/process/source-lock guards. The common verifier pins all eight
source query identities and preserves its bounded replay histories.

This packet does not register a complete Graphics capability. The full observer,
actor publication, background/restart/new-process ownership and combined
UI/QML/XHR/HTTP/Web-renderer/scene/capture quiet retirement remain required.
All native C++ sources are uncompiled and every device is untested. Host tests
use synthetic native/toolkit/GPU/OS boundaries and owned temporary files or
short-lived loopback fixtures only. Reconcile shared readers/versions with the
frozen Phone branch explicitly; its default fixture and mono path are unchanged.

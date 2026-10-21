# Ordinary Pico Graphics and Go To input surface

`pico-graphics-input-surface` v1 composes the existing `PicoNavigation`,
`PicoScriptIO`, `TokenGraphicsUI` and observed OpenXR `PicoTabletHome` gesture.
The original Pico adapter's private `_graphics_surface()` factory binds the
existing candidate/process/OpenXR session and requires native subject v3.
No complete `feature.graphics.*` operation is advertised by this component.

Before each possible mutation, the caller must durably commit its owning action,
the fresh original subject and a typed original input source (`navigation`,
`graphics` or `home`). A Home input retains its actual original geometry before
the one OpenXR primary gesture. Ownership callbacks reserve tablet/address
leases before input, and retire UI leases only after original UI absence/Home
facts. An uncertain result is never retried within this surface; the whole run
owner must reject replay of an issued action after process or call interruption.
Input receipts never become scene, preference, image or cleanup verdicts.

The surface opens the physical VR tablet, finds actual Home-page controls and
opens the original generic immediate Graphics page. It uses the actual observed
slider range/step and native Render readback through `TokenGraphicsUI`, including
normal scrollbar movement and motion settling. The separate Pico restart-only
swapchain setting is never substituted. A baseline outside the actual generic
slider grid cannot be restored through this input, so the whole owner must reject
it before changing preferences. The surface never rounds the original value.

Settings closure uses the actual ordinary Home ray before physical tablet close.
An owned page which was merely hidden is reopened to reach Home before retiring
its UI lease. An open or retained foreign tablet is not adopted. Original Go To
submission already calls the product's normal Home-and-close route; the surface
independently requires Home and field absence afterward. Backend QML/XHR/reply,
scene-load and Web lifetimes remain separate original sources, which must join
retirement and a quiet window before the whole owner deletes any journal.

`pico-navigation-address-observation` v1 adds an explicit optional native source
version to the original navigation snapshot. Its actual address TextField
contributes only its original UTF-8 hash, UTF-16 length and focused input-ready
state. Plaintext field contents are not added to the source. The source token
includes this actual observation, so a text/focus change retires an old token.
Legacy snapshots without the version retain their explicit closed reader;
the new Graphics surface refuses them before any input.

Each surface opts its own navigation instance into a caller-owned exact-address
authority. That explicit scope replaces its legacy configured URL set; no other
instance or operation registry is widened. Only bounded printable ASCII,
fully encoded HTTP(S), file or Overte addresses without userinfo/fragments are
admissible, with exact authorization checked again before delivery. The caller
must scope its actual registered scene ticket and exact original restore URL,
including any bounded viewpoint, rather than a hostname/prefix wildcard.

Address entry uses the actual GOTO button, normal focus, existing focused-field
Qt key input, and normal Enter. A successful replace ACK is insufficient: the
actual field hash and length must first match the scoped address. Enter requires
a second fresh current observation of the same content plus current authority.
The native token recheck prevents an intervening field/focus replacement from
being delivered. Ignored replacement, late content change, revoked authority,
lost return, failed intent and candidate replacement cannot submit an unrelated
or old address. No input script sets a QML field or invokes a feature method.

The current controlled Graphics scene preparation must already have its required
HMD first-person camera mode. `select_camera()` validates that current native
mode and returns no performed input; a different mode is unavailable until a
normal native View-menu operation is implemented. There is no Camera setter,
fictitious menu, fixed Phone eye or head-pose substitution. Whole Graphics
preparation/restoration must account for actual HMD transforms and per-eye GPU
projection separately.

All calls retain a 20-second operation budget, nested calls share that budget,
and existing bounded original UI waits remain in force. The surface does not
start, launch or repair a session, provide observer input authority, create a
fixture, change product behavior, or remove original evidence. Shared Home
binding is factored without changing Authentication's gesture or lifetime path.
Host cases exercise the actual Python composition at synthetic Qt/OpenXR/ADB
boundaries. Native C++/QML code is uncompiled and no device was accessed.

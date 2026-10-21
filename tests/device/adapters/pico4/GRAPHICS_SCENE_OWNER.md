# Ordinary VR Graphics scene ownership

The neutral `graphics-journey-scene` v3 owner reuses the frozen Phone scene
transaction architecture through an explicit platform policy. Its source hashes
and Git object identity are recorded in
[`FROZEN_REFERENCE.json`](../graphics_journey/FROZEN_REFERENCE.json). No Phone
worktree/WIP is read or modified. The Phone v2 journal remains a separate reader;
there is no implicit journal migration. The new header pins `pico-stereo-v1`.

`GraphicsScene.prepare()` requires an already first-person, visible/active
OpenXR source v3 with seven actually absent fixture UUIDs, complete raw scene
inventory, original avatar feet/orientation/scale and exact native framework
registrations. Foreign open UI, an already raised keyboard or an unrestorable
camera mode fails before scene input. `HMD.isMounted()` is the product visibility
API; this source does not independently qualify wear or hardware tracking.

The owner records the original scene URL, original avatar navigation viewpoint,
source packets and original committed request/deferred-load groups. A closed
ordinary action ledger reserves every Go To before delivery. Every controller,
Qt field and Home input first saves its actual native subject and typed input
source. Tablet/address/menu leases are distinct from native callback ownership.
Per-call source serialization and candidate/PID guards remain required.

The shared seven-entity scene is entered using normal Go To. Independently
observed entities and released committed loader groups are required after input.
Only exact native registered framework IDs are partitioned from the complete raw
scan; arbitrary local entities and names are never adopted as framework.

Alignment uses a second normal Go To: the original scaled/rotated HMD offset
from avatar feet supplies a feet target and compensating avatar yaw. Physical
head pitch/roll must already be within 0.03 radians of level; the observer does
not set Camera, HMD, sensor poses or entity geometry. The alignment's original
subject, computed feet and quaternion stay in the durable record and are
recomputed during archive validation. Readiness requires the actual head near
the authored view (0.02 m, explicit rotation-matrix tolerance), actual avatar
arrival and unchanged scale. Original stereo pixels remain separately required.

Lost input returns and interrupted processes preserve issued intent. Recreating
an owner can read original effects and continue a later unissued action, but
cannot resend the earlier Go To. Ignored input, held request groups, changed
native birth or a competing newer journal remain unavailable. Scene operations
are bounded to 45 seconds, each readiness wait to 20 seconds and action history
to 16 entries/128 input facts per entry.

`restore()` normally returns to the exact original resource and avatar feet,
yaw and scale, closes only owned UI, verifies all seven fixture IDs absent and
checks the original bounded scan region and unowned scene property hashes.
Tablet/keyboard/pointer registrations and appearance must match. Their raw
property hashes are preserved; tracking-driven geometry is explicitly excluded
only from the separate appearance comparison. Current physical head motion is
checked through its actual HMD/camera relation rather than confused with moving
the restored avatar. `retire()` rechecks restoration and actual journal absence.

This is an internal durable owner, with no public complete Graphics triple.
Actual UI roots, QML/XHR/reply callbacks, Web renderer/EGL workers, original PNG
and metadata file ownership, role captures, independent actor, restart and
three-second quiet retirement must still be joined by the complete coordinator.
Native compilation and all device/VR behavior are unverified. Host source models
exercise the real Pico navigation/token surface with synthetic native boundaries.

## Qualified restart framework baseline

Scene owner v4 retains the v3 journal reader. Pico restoration policy v3 keeps
the old scene/avatar/unowned inventory originals intact, while a separately
qualified restart handoff supplies the original framework registrations from
the new process. The exact handoff still requires the original old-PID ESRCH
receipt, native birth/lifecycle and owner-file binding. New framework IDs are
compared with that process's baseline; they are never relabelled as old IDs.
A foreign/future/old-process baseline, changed current framework appearance or
changed original world/avatar/unowned scene remains unavailable. An archive
counterexample exercises the actual scene decoder, original RestartInputs
protocol and independent presence/load packets; unknown old-process presence
cannot qualify restoration.

The restoration check now compares the complete original sensor-to-world
matrix. Its affine validator returns a scale, which alone cannot detect an
unchanged-scale world-origin shift. Actual physical sensor/head movement remains
permitted when the restored world transform and independent camera/head relation
remain valid. This source policy does not supply normal restart input/recovery,
the feature coordinator or device qualification. Native source is uncompiled.

Pico restart-proof v2 explicitly selects `pico-native-qt-bridge-v1`: the actual
NavigationUi constructor creates a new bridge UUID in every process. The new
binding preserves candidate/target and host generation zero while replacing
both PID/start and native Qt bridge identity. The legacy v1 receipt reader
still enforces its original preserved-session rule. Neither reader infers PID
death from a bridge change or an input acknowledgment.

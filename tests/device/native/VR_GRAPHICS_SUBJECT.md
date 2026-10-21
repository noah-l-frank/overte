# Original Pico VR Graphics subject and owner inventory

`native-graphics-subject` v3 extends v2's original entity/view/avatar source with
actual HMD transforms and authoritative framework ownership. Its reader retains
v1/v2 explicitly; the Pico factory requires v3 and cannot opt down through a read
flag. Other platform producers remain v2, without requiring Pico fields.
`vr-graphics-framework-ownership` v1 describes the additional pure validation and
partition. Neither source alone is a full Graphics capability or cleanup verdict.

All native additions require both `OVERTE_E2E_FEATURE_TESTS` and
`ANDROID_APP_PICO_INTERFACE`. The existing test-script/results launch gate,
fresh nonce, process birth, bounded observer history and candidate/OpenXR guard
remain in force. Native code is uncompiled and no real VR device is qualified.

The GUI-owned native subject reads the original MyAvatar sensor-to-world and HMD
sensor matrices. It preserves both column-major matrices and the actual world
head position/rotation calculated by the same original transform used in HMD
first-person camera updates. Avatar feet/orientation/model scale remain separate.
The active display name/type/visibility and original HMD `isMounted()` result
are observations. That existing mounted API derives visibility; it is not a new
physical tracking/wear-sensor qualification or successful-frame verdict.

The host checks finite affine transforms, uniform positive world scale, rigid
sensor pose, determinant/orientation and actual world transform consistency.
`first_person_head()` independently joins the current first-person camera to the
current native head. It never demands a fixed Phone eye height, freezes physical
head pose, changes Camera or treats avatar feet as the headset position. Actual
GPU cameras after late pose correction/jitter remain the separate render source.

Actual owner slots are read from the existing HMD tablet, native Keyboard and
PointerManager. The tablet includes frame, screen, Home button/highlight and mini
tablet frame/screen. The keyboard includes its complete original ignore-item set,
anchor/text display and the back plate omitted by the public `getKeyIDs()` API,
plus actual raised/use-3D state. The observer reads it on its original QObject
thread, without keyboard input, loading, cancellation or product state changes.

The manager and each pointer use nonblocking original read locks for a single
bounded inventory. Contention is unavailable; the observer never waits while
holding a manager lock for a pointer writer. Unknown pointer implementations
return unavailable, without an empty-owner fallback. Every Laser/Parabola normal
and default state is included with exact original start/end/path entity UUIDs.
A parabola's GPU render item is not mislabeled as an entity. Stylus records its
actual immutable model entity. It deliberately reports no current legacy stylus
render-state string: that product setter lacks a matching lock, and the observer
does not add a product synchronization fix or an atomic-state claim. Current
base enablement and original entity hashes remain independently available.

Each pointer retains its original manager/pick ID and hash of its actual native
creation-parameter map. That hash is neither source-code nor creator identity;
unsupported function values are subject to the original Qt JSON conversion.
It cannot authorize a replacement pointer after restart. Custom pointers remain
in the exact owner inventory and must not be silently treated as known system
scripts or omitted from restoration checks.

Every registered non-null entity is queried directly, even when hidden, absent
or outside the spatial scan. Present framework entities must actually be local;
no deterministic fixture UUID or fixture-parented entity can be adopted. A
bounded sorted inventory preserves actual presence/type/parent and two hashes:
the original full Graphics property projection and an appearance projection
which removes only position, rotation, dimensions and visibility. Raw names,
URLs, keyboard text and native pointers are not added to the exported inventory.

The complete original spatial scan is retained without exclusions.
`separate_inventory()` derives a separate exact-ID partition using only present
entities from actual owner slots. A local entity, a plausible keyboard name,
an absent registered entity or an arbitrary unowned object is not excluded.
Changing motion-dependent framework hashes remains visible in the originals;
the appearance hash alone never proves restoration. The whole feature owner
must additionally check actual owner/configuration continuity, original avatar
restoration, head/camera relation, UI/input lifetime, actor and quiet-window
sources, as well as unchanged scene entities outside the exact registered set.
Across an explicit restart, original death/new birth and structural provenance
must be joined before any new IDs can be adopted; this partition performs no
such adoption and no implicit migration.

Bounds include 128 pointers, 64 normal and 64 default states per path pointer,
128-byte native state names, 64 KiB original parameter JSON per pointer, 1,024
keyboard entities, 2,048 registered framework entities, the unchanged 1,024-entry
raw scan, 200,000-byte native source and 262,144-byte transport. Unknown types,
missing slots, bad matrices, fixture/foreign ownership, malformed history,
downgrade, contention or quota exhaustion stay unavailable. No cap is widened
and no old original is evicted to make a feature pass.

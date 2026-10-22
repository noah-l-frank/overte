# Original Pico avatar source

The private `_avatar_render_observer` factory reuses the committed shared
`NativeAvatarRender` version-1 source from Phone reference
`abb7f6b60d97daf17752aadf94e2b5df099bb7ba`, originating in
`f84dd87eb66f7fd2652710f1fef31f4e006b7890`. No Phone platform adapter, mono
capture or moving worktree was imported. See the
[selection record](PHONE_SHARED_AVATAR_SOURCE_20261022.json).

The gated original native getter reads the existing AvatarManager, original
SkeletonModel and loaded HFM geometry. It cannot instantiate a missing manager,
load an avatar, change visibility, set a camera or synthesize a requested asset.
Original model and geometry births are independent UUIDs; copied/reassigned
geometry does not inherit another object's identity. The Rig ID joins the
separate original animation source. Loaded originalURL hashes preserve the
actual consumed source without publishing its path. Original feet, orientation,
scale, camera mode and central recording frustum remain measured values.

The existing private native command transport carries only a closed read
request. The original probe forwards its result once to the mode0600 writer;
a missing native method remains unavailable. The reader preserves native birth,
PID, query sequence, original requested/captured times and source values. It
refuses missing, stale, foreign, oversized and nonadvancing originals, lost
candidate ownership and slow final guards/copies. The final original device
clock is reread after retaining the source, including with a frozen host clock.
Historical restore advances only the original cursor and sends no query.

This source supplies no image or visibility verdict. A central camera cannot
replace either Pico eye. The next capture join must bind this model/geometry
and Rig to the actual executed model draws, both original per-eye cameras,
original stereo PNG and successful same-frame OpenXR submission. Independent
actor/effect ownership, current challenge pixels and whole cleanup remain open;
no complete Emote capability is added.

The focused Qt5 check compiles the complete original getter body and original
model/geometry/Rig identity fragments, exercises missing manager/runtime gate,
original values, replacement, malformed commands, unloaded geometry and actual
cross-thread Qt delivery. Avatar/geometry/Rig/camera implementations are explicit
seams. Full Model, Geometry, TSI, GPU and application compilation is unverified;
no physical/device run was performed. The host reader/probe/fixture tests are
owned by the existing `emote-original-sources` group; the actual Pico factory
counterexample belongs to `normal-emote`.


The local optional native-avatar-camera-state v1 extension adds measured HMD
state, actual MyAvatar boom length and original minimum/default constants. The
base Avatar v1 contract and old readers remain compatible through explicit
optional fields. The strict reader rejects partial/coerced/foreign fields; no
legacy source supplies an assumed boom or HMD state. The normal HMD View owner
requires this original observation to avoid overwriting an existing custom
first-person boom. The whole getter/actual getBoomLength/constant fragments
compile in the existing Qt5 harness with explicit original Avatar/app storage
boundaries. The real camera mode transition has its separate original
QML/QAction/Camera method harness. Neither check establishes HMD/stereo or full
application qualification.

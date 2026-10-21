# Phone original projected-avatar pixels, version 1

`overte_phone_emote_pixels` measures actual pixel differences in the projected
avatar bound and requires a stable independent background control region. It
reuses the original world-PNG verifier, common 128-bit challenge/subject checks,
Graphics world-box projection and the new original avatar/model-draw join.
It implements no input, resource acquisition/repair, publisher or complete Emote
capability. Controlled scene/content, durable acquisition/image ownership,
Rig/input causality, independent actor and whole cleanup remain required.

## Exact originals and derived regions

A frame is exactly `ticket`, `avatarBefore`, `avatarAfter`, `capture`, `draws`.
All four native packets retain their full original identities, versions,
timestamps, view, actual loaded model/source, executed draw table and exact
PNG/pixel digests. `original` validates those joins plus the complete original
RGBA PNG bytes. The actual world-space model AABB is projected through this
exact captured view's original row-major matrix. All eight corners must be
inside the perspective frustum; tiny (less than 24×48 pixels), offscreen,
behind-camera or flat bounds are unavailable. No guessed FOV, camera alignment,
image resizing or default body rectangle replaces those original bounds.

The existing external image policy remains exactly `source`, `marker`,
`subject`, with `source:"world-render-target"`. Its subject must cover the whole
projected body bound and have at most twice its area. Its marker must be disjoint
from that bound. Existing challenge decoding still requires all 128 current
run/ticket bits; the existing nonuniform-subject check also applies. These
conditions do not certify unobstructed fragments: the full owner must validate
the controlled scene/content and exclude foreign occluders or unrelated motion.

## Pair comparison and controls

`measure(run,frame,png,policy,pid,epoch_ms,guard,previous=...)` accepts an optional
exact previous `{frame,png}` original pair. The full owner must reopen its
identity-bound immutable originals and PNG file before calling this pure join.
A caller-provided memory object alone does not establish file ownership or
durability. This function does not replace the existing image/resource owner.

The pair must have the same actual native capture context, loaded avatar Model/
Geometry/Rig, source, pose, camera mode and recorded view, identical original
source/viewport/target extents, strictly advancing capture/acquisition/avatar
query sequences, ordered native times and a different original GPU frame and
ticket. The common subject-change assertion must pass independently.

The union of both original projected bounds defines the measured body ROI.
Actual RGB differences above 25 must affect at least 5% of deterministic body
samples. A separate control region covers the image outside that union plus an
eight-pixel rim and the challenge marker plus a four-pixel rim. At most 1% of
control samples may change by more than 25. At least 1,024 body AND 1,024 control
samples are required. Each deterministic grid has at most 65,536 samples;
stride selection accounts for rounded row/column counts at awkward extents.
Both exact sample counts/strides and measured fractions are returned. These are
sample statistics, not a per-fragment avatar mask or all-pixel counts.

Thus a new marker over a frozen body, a moving camera, or broad background
changes cannot satisfy this pixel comparison. An in-place mesh/material edit
or another cause within the body bound is not classified as an Emote merely
because its pixels change: actual original selected-VM/Rig/input effects must
still be joined by the complete owner.

The result is exactly `emotePixelsVersion:1`, `ticket`, original `frameId`,
`imageSha256`, actual `modelInstance`, `geometryInstance`, derived `bodyRoi`,
`beforeTicket`, `beforeImageSha256`, `sampledBodyPixels`, `sampledControlPixels`,
`bodyStride`, `controlStride`, `bodyChangedFraction`, `controlChangedFraction`,
`subjectChangedFraction`. A single current image has null comparison fields and
zero samples; it never invents a motion verdict. There is no animation name,
requested pose, visibility verdict or `passed` field.

## Timing and qualification

Five seconds bound the full operation, including PNG decode, native/source
validation, sample loops, copy and final guards. Current original frame/source
freshness stays within 1.5 seconds using native and host monotonic age floors.
A frozen device clock cannot hide slow final work. The previous image stays
historical with its own timestamps; it is never retimed as current evidence.
Input/provider phase, native Rig/code, resource retirement and independent actor
freshness are the complete coordinator's additional obligations.

Sixteen registered Phone host tests use real original PNG bytes and projection/
comparison logic with synthetic native boundaries. Counterexamples include
marker-only changes, frozen/blank bodies, stale/foreign/missing PNGs and draws,
changed model/geometry/camera/projection/viewport, broad background changes,
offscreen/tiny/flat bounds, invalid policy, nonadvancing cursors, guard loss and
slow final delivery. These test the measurement logic only. Native code remains
uncompiled, full Emotes remains incomplete, and devices remain unqualified.

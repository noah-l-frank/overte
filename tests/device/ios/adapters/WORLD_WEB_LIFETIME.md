# World Web cache and final process ownership

This is a source and original-observation prerequisite. Whole World Web remains
gated until its foreground scene owner and paired final process archive compose
these sources. Native code is uncompiled and no device was exercised.

## Actual cache boundary

`Application_Setup.cpp` acquires HTML Web Entities from
`OffscreenQmlSurfaceCache`. Ordinary release pauses the surface, disconnects the
renderer, sets the root URL to `about:blank`, returns it to the cache and drops
the renderer's surface reference. It does not destroy the cached QML root or
its `IOSWebView` QObject. The actual renderer acquisition has its own
`_webSurfaceLease`; queued root callbacks also hold that lease until their real
connection/callback ownership ends.

`IOSWebSurfaceOwnership.h` records only actual cache build/push/pop operands and
actual renderer lease operands. It retains weak surface/lease references and a
zeroing root pointer. Distinct native UUIDs identify surface, root and renderer
lease births; pointer addresses are never serialized. Root creation is recorded
at its original Qt signal. The read getter does not promote weak references,
create a dependency, reset counters, drain queues or mutate the cache. The
read-only `IOSWorldWebSurfacesObservation` requires the existing dependency and
the unchanged native read bracket.

The closed native source has at most 512 surfaces, 2048 renderer acquisitions
and 8192 events, plus a 240000-byte actual compact-source ceiling. Overflow,
including this byte ceiling, off-main access, missing original operands or an
unexpected root replacement permanently make it incomplete. The existing
native bracket also retains its stricter actual serialized-size boundary;
source capacity does not enlarge that boundary. A live root or a queued lease
after release remains live in every original. Reacquiring the same cached root
produces a different actual renderer lease birth. There is no assumed weak
death from an Entity deletion, model removal, URL change or transport ACK.

The standalone action is `feature-ios-world-web-surfaces`, with exactly
`schemaVersion`, `commandId`, `action` and `runId`. Its bracket schema is
`iosWorldWebSurfacesVersion: 1`, domain
`native-main-ios-world-web-surfaces`, with the exact original
`iosWebSurfaceOwnershipVersion: 1` source. The Python reader is
`IOSWorldWebSurfaces`; the proposed native getter is
`featureIOSWorldWebSurfaces`. Shared Test/probe/fixture/factory routing is a
separate parent-owned integration and is not claimed by these files.

## Foreground quiet is separate from final release

World Scope writer 2/read 1,2 preserves the ordinary Script Stop/Home/file
cleanup. Version 1 retains its original full-drain behavior. The additive
common `quiet_web` hook defaults to the old full drain for Emote and Avatar;
only World Scope 2 chooses `world_web_resource_disposition.disposition`.

That disposition requires original callback return and actual policy-grant
retirement. It keeps every original resource counter and reports `held` when
any original holder survives. It does not assert QObject, WK object, software
image, QSG node, texture, Vulkan object or process absence. In particular, the
native bitmap carrier follows the original QImage's last implicit copy, and
`FeaturePaintNode` follows the actual parent QSG node. Those instrumentation
tokens must neither retain a product object nor pretend that a cached object
has died. The original image trace releases its actual QImage copy before its
lease ends; no consumer changes that native lifetime.

The whole foreground owner must join original Entity/renderer-lease ends,
actual WK view teardown and revoked document, original callback/input quiet,
ordinary worker terminal evidence, actual file absence, original restored
pixels and the four-clock quiet interval. All cached image/resource holders
remain owned. The public scene cleanup does not retire those holders.

After actual shared fixture retirement, a separate World finalizer must retain
both roles' original held groups, persist one canonical Stop intention, and
obtain each role's independent existing-SDK OS/DVT numeric-PID absence window.
The native counters remain unchanged after process death. No foreground
factory, invented zero inventory or second Stop is permitted. Exact immutable
archives, recovery ownership and the independent SDK DELETE/GET-404 boundary
remain required. This follows the existing Graphics two-stage protocol;
`WORLD_WEB_LIFETIME.md` does not itself implement that coordinator.

## Existing Emote boundary

Emote currently uses the common full-drain cleanup and its final archive is
qualified before canonical Session Stop. It has no separate held-cache to
OS/DVT final layer. The real cache finding therefore leaves Emote partial;
its old synthetic all-zero host model is insufficient to restore capability.
A separate Emote change must compose its own original held groups and final
process owner before its common drain policy can change. World changes do not
silently loosen the existing Emote or Avatar path.

Four host cache/weak-object cases cover cached-root survival, actual queued
lease survival until its final copy ends, distinct reacquisition, unchanged
original prefixes, invalid/incomplete sources and no weak resurrection. Three
disposition cases retain nonzero bitmap/QSG counters and reject pending
callbacks/grants or missing full admission. Native source checks only inspect
the C++ weak-reference and original-image lifetime implementation; they do not
claim native execution or actual QObject/QImage destruction.

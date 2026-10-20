# Avatar/people source contract introduced in v12

This is shared test logic and an exact adapter handoff, not device acceptance.
The three platform branches have no complete Avatar/people capability triple.
Native code remains uncompiled and no device has run these assertions.

## Normal inputs and controlled resources

Use the actual running Avatar application's normal URL, bookmark, scale and
wearable controls. `avatar-a.fst` is the hash-pinned original repository
Mannequin avatar with its complete relative FBX/texture dependency inventory.
`wearable-add` supplies the owned ticket's `gltf-bundle/main.gltf` URL, including
its actual mesh/image companions. `scripts/system/avatarapp.js` creates a Model
entity from that URL, attached to the actual MyAvatar session and the joint
whose runtime name is Hips. Never import entity JSON or assume joint index 63.
Record the actual returned entity ID before subsequent effects/cleanup; a
matching requested URL, pending resource or acknowledged button is insufficient.

Save the bookmark before changing scale or adding this owned wearable. The
prepared isolated profile has known scale 1 and no owned wearable; preserve
any independently captured unowned avatar entities. Do not wipe user entities
or replace real bookmark contents with assertion data. Owned names are exactly
the expanded run name. Existing unrelated bookmarks must remain unchanged.

`missing.fst` is an actual HTTP 404 for this run/ticket. Capture the original
request, response and native model failure. A fixture GET made by the adapter
does not prove that the product consumed that response.

## Nine independently observed fields

`requestedAvatar` is the original advertised skeleton URL mapped to
`original`, `A` or `missing`. `avatar` is the actual currently loaded geometry
resource mapped to `original`, `A`, `unavailable` or `fallback`. `modelLoaded`
requires the original skeleton resource and geometry/rig readiness, not a
nonempty model URL. It is false exactly for `unavailable`. `fallback` requires
the actual loaded default avatar resource; a default URL merely scheduled for
loading is still unavailable. Preserve the original initial model identity.

`loadFailed` means that an actual native failed-load event belongs to the
current advertised owned missing request and its original model generation.
It survives that generation's actual fallback. It becomes false only after a
new requested model generation is independently observed. An older failed
request, unrelated entity failure, HTTP request alone or current missing URL
alone cannot supply this flag. Do not fabricate a dismissible network popup.

`scale` is the actual settled avatar scale, also measured at the real peer.
`wearable` means the original owned Model entity is present, parented to the
actual avatar/Hips and actually loaded; independently inspect its resource,
attachment and peer-visible geometry. It does not mean that all user wearables
are absent/present. `bookmarked` requires an independent enumeration and read
of the actual owned bookmark. `connection` requires the original real backend
relationship state plus the actual pending consent protocol. `dialog` is the
actual current consent surface, independently read rather than copied from
the requested action or peer state. All nine fields require independent facts.

`Model::setURL` removes prior geometry. `Avatar::setModelURLFinished` can load
the default model while deliberately leaving the advertised failed URL alone.
The failed checkpoint therefore requires actual unavailable/fallback geometry,
the advertised missing URL and an original failed event. A retained A cannot
pass. `AvatarBookmarks::loadBookmarkInternal` waits for actual onLoadComplete,
then clears/restores saved avatar entities and scale. The next normal bookmark
selection must recover loaded A, scale 1 and no owned wearable. Failure receipts
from the prior request cannot be relabeled as current successful load evidence.

## Mutual connection backend and peer

Use two distinct signed-in fixture principals and two actual avatar session
IDs in the same controlled domain. The source protocol is
`scripts/system/libraries/peopleConnection.js`, composed by `pal.js`. Original
invite/accept/ready Messages coordinate consent but do not create a connection.
Only the actual HTTPS `/api/v1/user/connection_request` response, bounded
pending polling and fresh independently read relationship rows can establish
success. Both participants must consent. Cancel before peer acceptance and
peer rejection must preserve no relationship through the full negative window.
Remove through the normal control and verify actual DELETE success and refreshed
relationship absence on both accounts. The existing account fixture must be
extended for this real protocol; it does not yet supply these social endpoints.
Do not add endpoint setters, TLS trust bypasses or simulated acceptance peers.

## Deadlines, evidence, failures and cleanup

Use existing per-checkpoint 20-second observation deadlines, fresh run/ticket
barriers, native clock/PID/source continuity and the existing independent
publisher channel. Actual failed-resource retries/fallback must be observable
within that bounded window; no silently extended retry or synthetic failure is
allowed. Cancellation/rejection/deletion retain the existing three-second quiet
window. HTTP, peer and native original histories remain private and bounded.
Actual current challenge screenshots prove loaded avatar/scale/wearable changes
and failure/recovery; request acknowledgments never prove rendered geometry.

Cleanup twice through the existing owner: restore the captured original avatar,
settled scale and unowned attachments; remove only the original owned wearable,
bookmark and relationship; revoke owned backend authority and release original
peer/observer leases. Independently read restored state and empty owned-resource
inventory for three seconds. Preserve unresolved ownership on failure so partial
cleanup cannot pass. Missing native failure history, peer/backend authority,
geometry, input profile, independent publisher or cleanup keeps the complete
area capability absent. Host simulation exercises assertions only.

The v12 packet passes 778 explicitly selected common host checks, including
three Node checks of original Avatar handlers and new failed-model, missing
failure, stale/partial bookmark, ignored wearable and independent-witness
counterexamples. Compiler-dependent checks were excluded; no compiler launched.

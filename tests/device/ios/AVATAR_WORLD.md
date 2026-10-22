# Avatar world originals

`ios-avatar-world` and its acquisition record write/read version 1. The native
getter observes actual Domain/AvatarMixer/session identity, the complete entity
tree, submitted Script originals, actual mesh bounds, feet/orientation/velocity,
camera frustum and orbit properties. The closed command supplies only its
nonce and run ID.

The Avatar marker collection filters actual Script effects by the fixed
`avatar-marker-v1` profile. A separate native bracket records its real source
type and clocks. The existing Emote marker collection, original DTO, native
bracket, fixed `emote-marker-v1` filter and API remain unchanged. Both wrappers
call one private read-only common native getter. No caller selects a profile,
expected entity ID, pose, model URL or camera value.

This separate marker collection is needed because the original Emote getter
correctly excludes Avatar-owned challenge entities. Domain and other shared
fields retain their actual values; changing a namespace is not evidence of an
Avatar effect. Peer archives continue to retain the unchanged original World
DTO for domain identity.

Host tests exercise the actual FeatureObservation factory, fixed AFC path,
native-clock binding, strict fixture route and JavaScript consumed-nonce
dispatcher. An unavailable read remains unavailable and its nonce is consumed.
Source type/profile isolation, original Script UUID/tree joins, unknown bounds,
foreign marker properties, unowned entity changes and missing real Domain or
mixer fail closed. Native code is source-only and has not been compiled or
qualified on a device under the current task boundary. GPU sample ownership,
ordinary marker setup and complete feature cleanup remain separate work.

Avatar World v1 also accepts the optional typed `bodies` component,
`native-avatar-body-collection` version 1. It records the actual complete
AvatarManager collection with original session/self/replica identity and actual
world root position, orientation and velocity, even without loaded geometry.
The collection is captured inside the Avatar native bracket, with its own
original instance, monotonic sequence and native epoch. Legacy v1 originals
without this component remain unchanged and cannot supply unavailable-subject
physical continuity. A returned body collection cannot disappear or reset its
birth/sequence in a later original. The separate Emote native getter and source
shape remain unchanged. These transforms are not mesh bounds or expected
avatar geometry.

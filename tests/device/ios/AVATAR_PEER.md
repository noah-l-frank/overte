# Avatar peer originals

`original-avatar-peer-sources` version 1 extracts the immutable peer-source
owner from committed `54d48ae5d9`. Its Emote facade retains the original API,
filenames, version-1 envelopes and raw source DTOs. The Avatar facade uses
separate `avatar-peer` archives and role-qualified ownership files, and binds
the actual `avatar-people` phase reader. Avatar envelopes explicitly record
the actual SDK role; Emote envelopes retain their previous shape.

Each acquisition retains untouched World, received AvatarMixer packet and
renderer originals inside one native clock bracket, with separate host time
measurements. World remains its original native DTO: a source name does not
declare an Avatar or Emote verdict. Requests never supply expected model URLs,
avatar identities or poses to these readers. Renderer version 4 is required
for actual remote external poses and loaded-model world bounds.

Private files and manifests retain their original bytes, hashes, permissions
and inode identities. Storage and each acquisition step are journaled before
the next external call. An interrupted acquisition remains pending and cannot
be replayed as a whole read. Historical references resolve only to the saved
original. Crossing the actual phase archives the originals before refusing
the observation; a new phase is never attached to an older acquisition.

Host verification exercises independent frozen Emote-v1 data, Avatar namespace
and role isolation, actual private files, replaced-inode refusal and pending
read ownership. Native readers and SDK acquisition boundaries are controlled
host seams in those tests. The archive alone supplies source ownership.

`avatar_peer.replication` joins those separate originals to actual primary and
actor state, received sender metadata and the actor's loaded remote model,
external pose, joint layout, Hips and world bounds. It checks actual domain,
mixer and self identities and requires distinct candidate-bound SDK targets
and sessions. Wearables require their original owned entity IDs and actual
geometry; removal requires complete-tree absence. Missing models require an
actual fallback resource or actual unavailable geometry. Native epochs stay
within each process; cross-process epochs are never compared or retimed.

Runtime factories use each role's actual existing SDK and fixed native receive
file. Host tests exercise joins without motion, model failures, stale or
foreign metadata and attachment presence/absence. The complete Avatar feature
still needs whole-flow integration, social consent, GPU originals and quiet
cleanup. Native compilation and device qualification remain unverified.

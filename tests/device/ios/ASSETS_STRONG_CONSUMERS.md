# Original Assets mesh and material sharing groups

This packet extends the original Geometry observation with the actual shared
ownership of its graphics meshes and NetworkMaterial objects. Geometry death
alone cannot establish their absence: an independent renderer or another
consumer can retain a shared mesh or material after the Geometry releases it.

The focused host source/ownership cases now pass10/0.303s and the previous
Origin1–3/Geometry3 cases pass24/0.474s. No native compiler, renderer, device or
GPU has executed this instrumentation.

## Original source

History4 preserves all literal History1–3 fields and adds
`consumerOwnership`, a version1 inventory. The existing accepted resource,
mapping-resource and Geometry copy paths enumerate actual mesh and material
shared pointers. A resource that rebuilds its material vector is observed again
at its actual `setTextures` return. Each observation stores only weak ownership;
it acquires no permanent resource, material, texture or GPU reference.

Each row records an original UUID, the actual Geometry-row parent, mesh or
material kind, its actual vector slot, native birth clock and current
`strongOwnersAlive`. The first observed expiry clock is immutable. New sharing
groups at a reused material slot append new records. They do not overwrite an
earlier object or erase its responsibilities. Geometry identity follows the
actual lifetime token and original reader/mapping lineage; later observation
retains the original construction kind.

The existing128 Geometry-row,64 download,32 KiB body and64 KiB aggregate body
bounds stay unchanged. The new inventory is bounded to256 sharing-group rows;
capacity loss or a null/invalid actual group marks the entire original source
incomplete. Source construction bounds its temporary consumer list as well.
The getter still accepts only run and command IDs. It cannot receive a wanted
mesh, material, absence or cleanup result.

## Scope

`strong_consumers` reopens the validated original source and joins those rows to
the actual complete accepted parser/body/Geometry ancestry. A legacy or empty
ownership inventory cannot supply mesh-owner absence. Its distinct
`assetModelStrongConsumersVersion1` fact reports only whether all known original
strong ownership groups have expired.

The fact preserves the actual native sample epoch from its original carrier;
it never substitutes the host clock. Independent copies outside Geometry and
individually retained GPU buffers, TextureMaps or textures are not enumerated
by this narrow mesh/material sharing-group inventory.

An expired `std::weak_ptr` means zero strong owners. It does not establish that
the object's destructor has returned, queued renderer work has completed or a
GPU fence has drained. Both `destructorCompletionAvailable` and
`resourceRetirementAvailable` therefore remain false. Texture decoding, GPU/OS
allocation, callbacks, independently held materials and meshes, Actor/peer
observations, backend restoration, source/process and SDK ending remain
separate responsibilities. The earlier Geometry-release1 wire stays scoped to
its original Geometry/reader/resource/HFM consumers.

## Host qualification

The focused tests use real Python weak references to independently retained
mesh and material model objects. They require those holders to stay visible
after Geometry death, preserve original expiry clocks and refuse foreign,
mutable, malformed or lost inventory. Additional cases exercise the existing
original Probe through Node stdin and the canonical AFC/native-clock carrier.
These are explicit native-source models, with no C++/graphics execution.

Ten focused cases pass in0.303 seconds
(`assets-strong-consumers-ten-first-20261027.log`): the six new ownership/wire/
Probe cases, one actual canonical AFC/native-clock carrier case and three strict
Removal2/3/4 compatibility/effect cases. Twenty-four previous Origin1–3 and
Geometry3 tests pass in0.474 seconds
(`assets-strong-consumers-origin-legacy24-first-20261027.log`). The unknown
history negative now uses unsupported5; actual4 is a supported exact schema.

Registry `asset-model-origin-history` now writes4 and reads1–4. Distinct
`asset-model-consumer-ownership` and `asset-model-strong-consumers` write/read1.
No whole Assets journey, automatic cache eviction, complete transitive resource
inventory or native compilation is qualified by these narrow cases.

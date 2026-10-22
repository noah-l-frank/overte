# Pico Create original Model and resource source v1

Feature 4/14 remains **partial**. The private
`_create_model_resources_observer(target, run)` supplies passive original
Model, loaded Geometry, current material/channel bindings and NetworkTexture
state. It does not load a model or request a texture. The durable Model owner
currently proves the actual `textures` entity property separately; joining
these resource originals into that owner is the next composition step.

## Original path and admission

The closed `feature-create-models-observe` command accepts only schema version,
nonce, action and run. The native getter requires the existing dedicated
`OVERTE_E2E_FEATURE_TESTS`/Pico build, `--testScript`, private results location,
live original lifecycle, GUI affinity and already tracked actual Create IDs.
It never accepts a requested entity, model, geometry, URL, material or effect.
Dependency lookup requires existing EntityScriptingInterface and NodeList.

Actual EntityTree objects resolve their original RenderableModelEntityItem
`getModel()` association. The observer reads that GUI-affine Model's current
Geometry, original loaded HFM URL hash and actual Geometry material vector.
Each current material/channel maps its original slot name to the real
NetworkTexture object. Loaded source SHA-256 hashes the actual HFM URL bytes;
it is not a downloaded model-byte digest. Model/Geometry immutable identities
reuse the reviewed shared renderer identities, so subsequent actual draw
observations can bind the same objects.

The observer never calls `Geometry::areTexturesLoaded()`, which may mutate
opacity/material state, or `TextureSource::getGPUTexture()`, which may invoke a
texture operator. Resource URL, loaded and failed fields are plain original
Resource state read exclusively on the actual NetworkTexture owner thread.
A weak queued job and shared result use a cumulative 750 ms native monotonic
budget per observation; blocked/stopped owners refuse. Foreign callers reach
the original GUI receiver through a separate bounded 1750 ms weak queued job;
a request that expires before execution cannot capture a later observation.
A native nonce is consumed before acquisition, including unknown/timeout
results, and cannot recapture a later effect.

The packet preserves original process/launch instance, sequence, request and
capture times and actual DomainHandler connection birth/revision before and
after acquisition. Host continuity rejects same-UUID reconnects, replacement
launches, removed/reborn original identities and rewritten first-observed
times. The reader retains exact native JSON bytes and their SHA-256 through the
existing passive native reader. Unavailable sources remain unavailable.

## Weak originals and cache ownership

Histories are append-only and hold no strong Model, Geometry, material or
texture reference. Their first-observed times are acquisition times, not
invented creation times. Limits are four runs; per run 32 current entities,
64 Model identities, 64 Geometry identities, 128 materials and 64 textures;
per Model at most 64 materials and 128 current channel bindings. The native
getter has 512 frozen command nonces; source JSON is limited to 196608 bytes.
Exhaustion refuses acquisition.

Original `Resource::allReferencesCleared()` may reinsert the **same live
QObject** into ResourceCache with a new QSharedPointer control block. Expiry
of its old QWeakPointer does not prove death. Each texture history also keeps
a passive QPointer. A surviving QObject remains `alive: true`; if its original
shared block has expired, `sharedAvailable: false` and null state explicitly
preserve this boundary. A later actual material association to that same live
QObject may refresh the weak shared block while preserving its native history
identity and first-observed time. No cache lookup invents that association.
Only actual QObject death sets `alive: false`. Neither cache eviction nor
manual resource/Qt destruction is an adapter cleanup operation.

The source retirement helper requires no current Model association and actual
death of every observed original Model, Geometry, material and texture. Tree absence
alone cannot satisfy it. Cache-retained textures can therefore retain cleanup
ownership; future owner composition must preserve that result. This is a sampled inventory of the actually observed objects, not an event
log of every intermediate resource ever allocated between observations. A
complete allocation/assignment-history join remains required before claiming
whole-resource cleanup. Independent mesh/GPU payloads and script/Qt listener
lifetimes remain separate joins.

## Executed host checks and boundaries

`test_create_model_resources_native.py` compiles the original native getter,
observer, RenderableModelEntityItem association accessor, Geometry material
accessor and original `Resource::allReferencesCleared()` body. Qt5 and Qt6
execute actual QObject, thread, queue, semaphore, weak/shared reference and
deferred-deletion behavior. Explicit substituted boundaries are the EntityTree,
Model/HFM/Geometry/material load actor and ResourceCache container; no actual
model download, renderer or GPU is claimed.

Counterexamples cover foreign/missing arguments and dependencies, immutable
nonce results after a changed material binding, retained Model/Geometry after
Tree removal, actual QObject cache control-block rollover, actual deferred
QObject death, reused dead native identities, a blocked resource owner,
stopped resource thread, real worker-to-GUI delivery, an expired unserviced GUI
request that cannot later capture, and same-UUID Domain reconnect. Host packet
checks reject foreign resource/model identities, future births, missing
original histories, resurrection and requested extra fields.

This source does not prove original downloaded/decoded image bytes, GPU
texture upload/binding, completed stereo draw/capture, current visible pixels,
peer replication or full resource retirement on a physical client. Full native
translation units, real domain/client/Pico, OpenXR and GPU are unrun here. No
full `feature.create.*` capability is advertised. Registry adds only
`pico-create-model-resources` v1 and the additive
`create-model-resources-native` selector mapped to `tablet-and-create-ui`;
parent integration must add one to its actual current catalog count.

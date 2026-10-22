# Shared iOS feature-source integration, 2026-10-22

This local packet connects the source prerequisites for Avatar/contacts (3),
Create (4), and Emotes (5). Each area remains partial and its complete capability
stays disabled. Native sources are uncompiled and devices are untested.

The existing TestScriptingInterface, fixture command admission, probe, and
FeatureObservation HTTP/AFC transport now connect Avatar state and renderers,
Create state and owned files, selected script roots, and original AvatarMixer
receives. The native entrypoints retain the dedicated E2E build/runtime gates,
closed request fields, process ownership, and original counters and clocks.
Avatar renderer reads include actual evaluated remote Rig pose originals;
original receive records remain a separate source.

Create files accept at most 131072 command bytes, with separate bounded staged
input and original export bytes. The HTTP fixture admits this larger payload
only for that action; normal UI keeps its previous bound. Native storage records
intent before touching files and caches the first result, including unavailable,
for every nonce. The probe retains consumed nonces too. Delivery cannot establish
an import, export, release, or resource absence. Independent observations must
verify these effects before owner metadata can be retired.

Animation history writes v2 with native VM caller identity, while its reader
retains v1 compatibility. Avatar model completion retains the original geometry
assignment and generation across queued callbacks. Create adds passive original
texture-consumption bytes and gated read-only model accessors. Normal iOS Create
writes controls v2 and reads v1/v2; other platforms retain their v1 producer.
Shared registries retain these version boundaries for later Phone/Pico review.
See AVATAR_STATE.md and EMOTE_SOURCES.md for the exact native hook provenance.

Verification used explicit no-build host tests: 139 tests passed in the combined
source suite, followed by all six existing Create control tests with their
required sibling import path. The initial combined invocation reported one
module-import error for that path; its other 139 tests passed. Five project
suites, contract versions, Node probe syntax, and whitespace checks passed.
No compiler, device, simulator, installation, laboratory, or remote write ran.

Whole user flows, current image/peer evidence, interruptions/restarts, and
verified repeated quiet cleanup are still required for the three areas. This
packet also registers the separately committed durable Places action owner;
its ownership journal does not complete Worlds/navigation.

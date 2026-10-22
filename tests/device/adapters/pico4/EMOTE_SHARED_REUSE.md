# Reviewed shared Phone source for Pico Emotes

Pico reuses the original shared V8 compilation observation, immutable original
records, optional Script-source reader extension and its complete host test
module from committed Phone source
`abb7f6b60d97daf17752aadf94e2b5df099bb7ba`.
The [selection manifest](PHONE_SHARED_COMPILATIONS_20261022.json) records exact
original/target hashes and narrow native dependencies. The initial frozen Phone
baseline remains `fe4684bf46585088370b3a328a738f147e670b97`. No uncommitted Phone
work, moving branch, platform input/actor or mono image binding was imported.

[Original compilation identity](../../native/SCRIPT_COMPILATIONS.md) means the
actual V8 Script ID, name and UTF-16 bytes supplied at the existing Compile
boundaries, including includes in a shared manager. It is independent of the
requested filename or submitted top-level text. New original rows append;
prior IDs cannot change or disappear. An observed extension cannot downgrade,
even to an empty engine inventory or during historical replay. Legacy Script
packets remain readable. All old code/execution/HTTP/membership contracts and
private size limits remain unchanged.

The common implementation is used directly rather than duplicated in a Pico
parser. Narrow guarded native selections add only compile recording/publication
through the existing private Script source. Actual V8 Function/caller dispatch,
selected callback/timer work, Phone touch controls and Phone observers are not
part of this selection. Recording compilation proves neither execution nor an
Emote effect. Every native addition requires the dedicated E2E configuration
and active `--testScript`; native code remains uncompiled.

Next reconcile the pinned shared native animation data/caller/history/source
selection and readiness dependencies with the actual Pico default Script roots.
Use normal VR chooser/controller input, independently measured Rig progression
and original stereo avatar pixels. The independent actor and full interruption/
restoration/retirement path remain required before advertising any complete
Emote operation triple. Shared v17 motion/runner changes need their own reviewed
migration; this packet keeps the existing Pico v16 complete triples intact.


## Original animation bytes and consumed model selection

The [second selection manifest](PHONE_SHARED_ANIMATION_DATA_20261022.json)
now reuses the shared consumed-data parser, immutable twelve-FBX fixture pins,
weak native model registry and actual retarget/clip source observation from the
same fixed Phone commit. Pico preserves its original parser call and functional
behavior. The native observation hashes the actual parser input and the same
model reference copied into the clip; it never replaces that with a disk reread
or requested URL hash. The existing native feature/history v1 readers admit
this explicitly versioned optional source and reject future model/consumption
clocks at the containing original capture. Legacy clips remain readable.

This supplies original consumed-content provenance, not an animation or render
verdict. Passive cache readiness and compiled caller/source/profile joins are
still missing, followed by ordinary Pico VR input, stereo avatar evidence,
independent role publication and whole interruption/resource retirement.

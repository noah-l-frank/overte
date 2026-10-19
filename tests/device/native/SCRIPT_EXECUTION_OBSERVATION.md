# Native Script execution observation, version 1

The default-off `OVERTE_E2E_FEATURE_TESTS` option and an explicit `--testScript`
launch enable a read-only source for the existing adapter architecture. It does
not execute, restart, stop, require, include or evaluate any code on request.
No product functionality changes. The source is uncompiled and unqualified on
devices; current Python/JavaScript tests prove control logic only.

`ScriptManager::require()` records the **actual resolved module URL** at normal
successful instantiation, actual cache reuse or a normal fetch/evaluation error.
Each manager has a native random 32-hex identity. Its lock-protected module
history contains the last real event per URL: `url`, `loaded`, `cached`,
`sequence`, `capturedEpochMs`. A successful `module.loaded` assignment and a
cached module's actual loaded property are separate from successful source
download. Failures record `loaded:false`. Read requests never advance module
cursors or timestamps. This is require-event history, not a claim about the
current mutable JavaScript cache or a complete script exception ledger.

`ScriptEngines` snapshots its actual manager membership under its existing
lock, retains those managers while reading, and exports real source URLs and
atomic running/stopping/finished flags plus their protected histories. It
never synchronously invokes all script threads; the waiting probe's own
ScriptManager cannot deadlock a GUI observer that waits for it. A concurrently
stopping manager may still appear with its actual flags until the next read.
Consumers must establish the current owned running engine and actual advancing
entity effects independently; module history alone cannot prove an active loop.

The closed `feature-script-observe` command has exactly `schemaVersion:1`,
`commandId:<32hex>` (HTTP/AFC uses `ios-<32hex>`) and `action`. It has no desired
source URL, module name, code, expected companion or success value. The probe
calls only `Test.featureScriptObservation(requestId)` and publishes its original
packet to `feature-script-observation.json` via a private atomic 0600 write.
An unavailable hook/source publishes `available:false`, which fails validation.
No request ever loads the very code whose presence the test wants to establish.

The envelope is exactly `schemaVersion`, `requestId`, `instance`, `sequence`,
`requestedEpochMs`, `capturedEpochMs`, `processId`, `source`. `instance` is the
native feature instance; `sequence` counts only source acquisitions. `source`
is exactly `{complete:true,engines:[...]}`. Each engine is exactly
`{url,running,stopping,finished,required}` and `required` is exactly
`{instance,sequence,modules}`. A manager with no actual require has sequence 0
and an empty modules list. An event is timestamped only when that require
actually completes or reuses a module; its original time may predate this
observation legitimately. Request/capture clocks remain native clocks on iOS;
the bounded local monotonic acquisition and unique correlated request establish
the fresh join without relabelling historical module timestamps.

Bounds: 128 engines, 256 distinct module URLs per engine, 4096 characters per
URL, module cursor at most one billion, at most 262144 UTF-8 packet bytes, five
seconds and 51 reads per request. Native history/serialization budget failures
make the source unavailable, never truncated successful inventories. The host
rejects duplicate engine IDs/module URLs/cursors, malformed types,
foreign request/process/instance, missing entries and regressing histories.
It remembers at most 4096 native manager identities in one reader lifetime;
a disappeared/retired manager cannot reappear in a newly stamped packet.
Explicit restart is observed as a new real manager identity. Returned data
cannot mutate the reader's independent previous-history copy.

Two genuinely different native managers may overlap on the same source URL
during restart. The raw observer preserves them. `running_owned_engine()`
requires exactly one actual running, non-stopping, non-finished manager for the
full owned URL; it never chooses by basename or arbitrarily picks a duplicate.
`loaded_relative_modules()` derives aliases from actually loaded module URLs
inside that engine's original root. Foreign same-basename modules, pending/failed
loads and encoded parent traversal cannot become the expected companion.

There are no owned product resources to clean up for this read-only source.
Runner teardown retains/removes only the current run's private diagnostic file.
The caller must still cancel a real file picker, stop the owned engine, observe
owned effect/entity absence, and remove owned staged companions through its
ordinary feature cleanup. Never Stop All or delete unrelated imports.

The current complete feature contract is version 2; its Script picker and
actual companion/effect observer joins are not implemented merely by this
source. A full Script observer must map only genuinely loaded dependencies of
the current owned engine to the public `companions` names and independently
measure advancing effects. The module event's URL cannot come from the test's
requested filename. See `../feature_journeys/CONTRACT_MIGRATION.md`.

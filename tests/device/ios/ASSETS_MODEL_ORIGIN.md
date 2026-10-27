# Assets parser input and actual render-geometry lineage

The closed `feature-ios-assets-model-origin` source observes the actual world
Model wrappers and their current render Model, watcher URL and Geometry
lineage. Its query carries only a run and fresh request nonce; it accepts no
wanted entity, URL, hash, success state or operation.

The iOS feature-test hooks record the original ATP `downloadFinished` argument
before the existing URL mutation and parser dispatch. They do not fetch, read
the reply, rerun a parser or invoke a callback. Up to 64 original download rows
are retained, with at most 32 KiB per body and 64 KiB in total. Every retained
body includes the exact Base64, byte count and SHA-256. Overflow or a missing
body makes the history incomplete; diagnostics retain the original count/hash.

The actual `GeometryReader` owns a separate weak-observed first-member token,
which expires after all original task fields. Scope observations surround the
original `run()` and `setGeometryDefinition` bodies. The registry records the
actual processed HFM shared ownership before the existing `invokeMethod`, its
actual return value and the matching actual receiving Resource. Pointer text,
a current URL or a requested entity never selects queued delivery provenance.
Ambiguous delivery makes the history incomplete. No observation holds a
Resource, task or HFM model strongly across reads.

An accepted reader ID is copied by the original Geometry copy path into the
actual render Geometry. The existing FST mapping-success path copies the
child's accepted lineage and appends its own original mapping download ID.
The passive Model accessor exposes this actual lineage alongside the actual
Model and watcher URLs. The whole-tree bracket retains actual entity IDs and
rejects a changing inventory.

`parsed_input()` requires a complete original history, the actual loaded and
added Model, one actual linked reader, original body bytes, returned reader
and delivery bodies, and an accepted original dispatch. It reports a
`assetModelParsedInputVersion` observation. It does not establish that those
bytes are the independently read baked server output, that a pixel rendered,
or that an independent actor consumed the model. Those joins remain required.

The separate [retained parsed-input owner](ASSETS_PARSED_INPUT.md) joins these
originals to an independently retained baked backend body. This getter alone
still supplies only origin/reader observations.

## Retirement and qualification limits

History version 2 adds `resourceObjectAlive`, observed directly by a main-thread
`QPointer<Resource>`, separately from the original shared lease's legacy
`resourceAlive`. `Resource::allReferencesCleared` can create a new shared control
block for the same cached QObject; expiry of the old lease cannot prove that
object died. Original queued HFM ownership now matches the actual receiving
QObject, including that control-block distinction. The collector retains no
Resource/HFM/task strongly; no cache entry is removed or retained by this hook.
Literal history version 1 remains readable and supplies no object-lifetime
field. Version rollback, unknown fields and non-boolean object observations
are refused. The outer source and parsed-input schemas remain version 1.

`resourceRetirementAvailable` is always false. Resource/HFM/parser weak
liveness is observation only: cached Geometry, texture, decoder, GPU and
queued work inventories are not complete. No cache is cleared, resource
released or worker behavior changed. Loaded/scene flags and expired reader
tokens cannot retire the existing model responsibility.

These native hooks have not been compiled or executed. Host tests use an
explicit native/parser boundary model while running the actual source codec,
closed fixture route, JavaScript probe and candidate/PID/foreground/AFC
transport guards. The pinned FBX body is 25,196 bytes and remains unchanged.
No server, oven, service, compiler, renderer, device or installation executes.
Assets capability remains closed and source completion remains 5/14.

## Host verification

The nine codec/probe cases and three runtime/candidate cases passed 12/12 in
0.159 seconds; private log:
`.ios-host-tmp/assets-model-origin-twelve-20261026.log`.

The ten unchanged Create state cases and ten Assets runtime cases also passed
20/20 in 4.253 seconds; private log:
`.ios-host-tmp/assets-model-origin-compatibility-twenty-20261026.log`.

Contract-version validation and the five explicitly selected no-build project
suites passed (6.76 seconds); private log:
`.ios-host-tmp/assets-model-origin-project-five-20261026.log`.

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=.:tests/device:tests/device/self_tests:tests/device/ios/self_tests \
TMPDIR="$PWD/.ios-host-tmp" timeout 120s python3 -m unittest \
  test_ios_assets_model_origin.AssetsModelOriginTests \
  test_ios_assets_model_origin.AssetsModelOriginRuntimeTests -v
```

Counterexamples cover an unlinked loaded flag, unfinished/ignored delivery,
changed original bytes/count/hash, over-limit or missing bodies, foreign
entity/reader membership, invented retirement availability, changed old
history, stale native clocks, changed candidate/process/background state,
unknown command fields, reused nonces and a missing native getter.

The history-v2 selection passed 20/20 in 26.882 seconds: eighteen old/new
source/probe/AFC cases, the connected retained parser-input join and the
original-consumer immutability case. Private log:
`.ios-host-tmp/assets-origin-object-twenty-20261026.log`. Host weak-lifetime
cases use actual separate weak lease/object/HFM holders. The connected SDK
model's product cache owns the resource strongly, while the source ledger
holds weak references only; its original Model owns the separate original
lease. This prepares ordinary Model removal with the cache still observably
alive. The C++ source remains uncompiled/unexecuted and complete texture/GPU/
decoder retirement remains unavailable.
Contract-version validation and the five explicitly selected no-build project
suites passed in 6.75 seconds; private log:
`.ios-host-tmp/assets-origin-object-project-five-20261026.log`.

## Original Geometry consumer lifetime boundary

History3 adds a bounded, append-only `geometries` list to the existing source;
versions1 and2 remain literal readable histories and contain no invented
Geometry inventory. Up to128 records retain an original opaque consumer ID,
actual reader/mapping lineage, constructor/acceptance kind and native birth
clock. `alive` observes a weak first-member token. Its first observed death
gets a separate immutable `destructionObserved` clock; this is observed death,
not an invented destructor timestamp. Missing rows, changed original IDs/
lineage/births, reordered prefixes, rollback, resurrection and rewritten death
observations refuse continuity. Overflow makes the existing completeness flag
false rather than truncating to a successful inventory.

The native Geometry default/copy path owns the token as its first data member,
so destruction releases all actual Geometry fields before that token. The
registry keeps only weak ownership. Existing accepted resource definitions,
FST geometry adoption and copy construction register their actual already
assigned lineage. Copy registration can run on the original constructing
thread; it inspects standard weak ownership and immutable IDs under the
existing mutex, without reading QObjects there. Source snapshots still use
the original main-thread getter. No cache is emptied, parser repeated, Model
created, callback invoked or resource/Geometry/material/texture held strongly
by this observer. All additions are iOS/feature-test compiled and inactive
without `--testScript`.

`geometry_consumers(packet, reader_id)` resolves the reader only after the
complete original packet is acquired. The native command has no requested
reader/consumer/alive/retire selector. A complete accepted/returned parser and
at least one known actual consumer are mandatory; an empty or legacy history
cannot establish absence. The separate `assetModelGeometryConsumersVersion1`
returns original reader/body identity, actual Geometry records and independent
reader/original-lease/QObject/HFM liveness. `allKnownGeometryDead` describes only
those observed Geometry owners. `resourceRetirementAvailable` remains false:
external mesh/material/texture/GPU/OS holders and final whole-resource/SDK
retirement remain unqualified even if every known Geometry token expired.

The real-weak-reference host case retains an actual copied Geometry/HFM after
the old original lease and cached QObject die. Only releasing that copy makes
its token and HFM expire; prior packets and first observed death clocks stay
unchanged. Other counterexamples cover unknown/duplicate/oversized or untyped
inventories, impossible birth/death ordering, missing original consumers,
foreign mapping/reader IDs, prefix loss/reordering/rewrite/resurrection and
unsupported history versions. The actual full JavaScript probe preserves
History3 once per nonce; the existing installed/native-clock/AFC path retains
the unchanged original packet without app launches.

`assets-geometry-consumers-second-20261027.log` passes24 cases in0.462s:
five new weak/history/probe cases, one new canonical native-clock/AFC case
and the eighteen old Origin/probe/runtime/object cases. The first log retains
five passing new cases followed by a test assertion failure: the existing
runtime fixture had already launched once during setup. Comparing the launch
counter before/after the new read correctly verifies no additional launch;
no adapter or runtime behavior changed. The old unsupported-version negative
now uses4, because3 is explicitly supported with mandatory Geometry records.

Native code remains uncompiled and unexecuted. These tests prove Python/Node
codecs, declared weak ownership, packet immutability and modeled SDK transport;
they do not qualify C++ destructor ordering, real cache eviction, rendering,
physical timing or iOS devices. Next bind these original consumer records to
the already qualified ordinary removal/two-image parent, then implement actual
quiet lifetime drainage and the remaining texture/Actor/source/process/SDK end.

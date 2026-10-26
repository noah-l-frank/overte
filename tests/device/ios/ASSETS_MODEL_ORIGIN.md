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

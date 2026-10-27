# Assets actual Model mesh source

This passive source is a prerequisite for attributing original world pixels to
the actual imported model. It supplies no pixel, committed draw, callback,
cache, texture, decoder, GPU or OS retirement verdict. The full Assets adapter
remains closed and the completion count stays 5/14. Native C++ is uncompiled
and no native renderer, device, build or real service has been exercised.

## Default-off source boundary

The new `feature-ios-assets-model-renderers` action has only schema version,
fresh command nonce and run ID. Wanted IDs, geometry, URLs or observations
cannot enter the query. The getter is gated by iOS, feature-test support,
the dedicated iOS E2E test build, a live original feature lifecycle and
`--testScript`. Missing or failed native getters remain unavailable, with
the original nonce consumed. Older Assets origin1 and all existing route
defaults are unchanged.

`IOSAssetsModelRenderersObservation` enumerates the actual complete EntityTree,
then each existing ModelEntityWrapper's already owned Model. It observes the
current Model's flags, mesh payload bounds, actual allocated render-item IDs
and existing accepted-geometry provenance. It double-reads those facts and
checks the wrapper still holds the same actual Model; the complete entity
inventory must remain unchanged. No payload or Model is retained beyond the
read. It does not request a model, trigger parsing, apply transforms or invoke
a renderer. A changed or incomplete source is unavailable.

Bounds come from the actual mesh payload union in `getRenderableMeshBound`,
rather than entity-requested dimensions. Planar mesh bounds are accepted when
they span at least two axes; points, lines and invalid/nonfinite bounds cannot
become a model subject. Original mesh item counts are bounded per Model and
globally; bodies retain the existing 256 KiB source limit. The current Model's
accepted geometry reader and mapping identities are included in the same
double-read, so a later pixel join can bind that mesh to the independently
retained parser input. URLs or loading flags alone are insufficient.

Allocated Model render-item IDs are not proof that those items committed to a
scene or issued a draw. Current mesh bounds are not pixel evidence. Both
`renderedPixelsAvailable` and `resourceRetirementAvailable` stay false.

## Qualification and next dependency

- `assets-model-renderers-codec-first-20261027.log`: seven standalone DTO
  counterexamples passed in 0.003 seconds.
- `assets-model-renderers-original-geometry-20261027.log`: eight expanded DTO
  cases, including actual accepted-reader availability, passed in 0.004 seconds.
  These execute Python against declared synthetic getter packets, not C++.
- Shared Python routes parse/import and `node --check` accepts the actual
  modified probe.
- `assets-model-renderers-route-first-20261027.log`: thirteen cases passed in
  0.215 seconds: eight DTO counterexamples, one actual extracted Node/probe
  route (including nonce consumption/missing/throwing getter), four canonical
  HTTP/AFC/candidate/process/body-limit cases. The original native clock is
  independently bound; neither new session nor application launch occurs.
- `assets-model-renderers-origin-keyboard-compat-20261027.log`: twenty-one
  existing origin1/parser/QObject and keyboard transport cases passed in
  0.379 seconds. All existing default routes and original resource/object
  lifetime distinctions remain unchanged.
- `assets-model-renderers-project5-20261027.log`: all five explicitly selected
  documentation, documentation-contracts, iOS input-selection,
  policy-consistency and project-coverage suites passed in 6.74 seconds.
  Version consistency and whitespace checks pass. No native compilation or
  device/render qualification follows from these checks.

The next acquisition must join original fenced world-frame bytes to this
actual bound/reader/item source, unchanged complete scene and camera originals,
an owned fresh marker, exclusive subject pixels and ordinary model creation or
removal. A global forward-draw counter is insufficient for entity attribution.
The original Model and peer/cache lifetimes remain independently owned after
any successful image. Existing Create image/marker owners must retain their
own schemas and responsibilities, not be relabeled as Assets publication.

The private peer owner's conservative differing-PID admission also remains to
be qualified for distinct devices with coincident numeric PIDs. Its existing
candidate/source-instance identity checks must retain alias rejection when
that admission is widened. See [peer originals](ASSETS_PEER_ORIGINALS.md).

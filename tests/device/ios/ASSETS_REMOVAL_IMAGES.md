# Original Assets Model removal images

This is a partial Feature13 component. It does not complete Assets, advertise
a full capability, retire cached Model/HFM/texture objects or qualify iOS.
Native instrumentation remains uncompiled; devices remain untested.

## Existing owners and explicit observations

`adapters/assets_removal_images.py:compose` consumes one existing
`OwnedAssetsModelRemoval` and two existing `AssetsImageSample` children. All
three use the same held canonical lock, private directory, actual ParsedInput
parent and binding; both samples share the exact actual Marker owner. Requests
and GPU frame identities differ, while the challenge ticket is deliberately
the same. Construction, ordinary input and image acquisition remain in the
existing owners/runtime factories. The join itself sends no input, takes no
new image, writes no WAL and starts no process or transport.

Both sample journals and their saved logical/raw/PNG/GPU originals are read
again. Pending raw/logical acquisition, changed current journals, foreign
parents or an unclosed normal editor context refuse this join. The actual
Removal journal must decode as `model-gone`, with exactly its original Delete
intent, source observations and completed Home/context closure. The resulting
`assetModelRemovalImageChangeVersion1` contains the actual recomposed removal
observation and `resourceRetirementAvailable:false`.

The old present-image profile and `assetModelImageVersion1` remain literal.
`assets_model_images.compose(..., absence_basis=(prior_frame, prior_png))`
explicitly recomposes a prior genuinely present image before allowing an
absent image. This returns the distinct `assetModelAbsentImageVersion1`, empty
current render-item IDs and the actual prior `basisFrameId`/mesh bounds. The
old present-image profile continues to reject a removed Model. Existing
ImageSample1 capture/raw/logical schemas stay unchanged: the after sample is
`captured`, and is never falsely marked qualified by the present-image path.
The pure `pair` helper returns an internal tuple, not a normal-input receipt.

## Original time and pixel joins

Both native and host clock brackets remain their original values. Native
prefix validation orders the before image before the original Removal baseline
and the actual closed context before the after image. The corresponding host
epoch and monotonic brackets must agree in order. A restored or historical
archive does not refresh an image or inherit a current-clock verdict.

Create, Model-renderer and Avatar-renderer sources must be complete and share
the actual process/run/domain/tree. The subject Model is present, loaded,
rendered and bound to its actual consumed reader/mesh in the prior image; it
is absent from both subsequent Create and Model inventories. Only destroyed
editor roots are permitted by the explicit absent path; a live tablet/editor
still fails. Current GPU fence/read/retirement, original PNG bytes/pixel hash,
recorded view and the full same-ticket marker are independently checked.

The absent subject ROI is constrained by the prior measured mesh, with the
same current recorded camera and target extent. A uniform background can be
honest only on this explicit absent path; the actual bytes are decoded without
painting, filling or replacing pixels. The same 25-channel/5-percent subject
change threshold used by the existing image evidence contract is applied to
the actual prior and current crops. Unchanged pixels cannot prove removal.

Every unowned entity/tree entry, other Model mesh, graphics/lifecycle state
and Avatar/attachment semantics must remain unchanged across the pair. Only
Avatar sampling timestamps/evaluation counters are omitted from the semantic
comparison; their actual original source continuity is still validated and
all poses, joints, flags, rig IDs, URLs, scales and bounds remain compared.
Both images exclude other visible contributors from the subject ROI.

## Recovery and remaining responsibility

An uncertain Delete or Home remains the responsibility of the existing normal
Removal WAL. This observer never resends either input. Saved completed image
recovery uses the existing exact file/reference adoption; an unresolved image
query/GPU child is not silently recaptured under the same request. Existing
24-query/one-frame/image limits and twenty-second narrow-owner budgets remain
unchanged. Different requests are separate owned attempts, not a retry that
hides an unknown earlier delivery.

Even a successful image join leaves the original parser, cache/HFM/texture,
GPU/OS holders, Actor/peer publication and image, server/work restoration,
shared journey and process/SDK end obligations open. The normal local Model
absence and retired GPU image child do not retire those responsibilities.

## Exact host evidence

`self_tests/test_ios_assets_removal_images.py` uses newly emitted declared
native/raster specifications and actual PNG decoding. It executes no native
renderer or normal Delete. The six new cases cover actual absent/uniform
pixels, original prior bounds, literal present-profile refusal, unchanged
pixels, wrong challenge, foreign/reused source/frame/camera/graphics/Avatar/
Marker/tree/GPU data and unrelated typed helpers. Together with the six old
present-image cases, `assets-removal-images-final-pure-20261027.log` passes
12 cases in0.847s. The earlier first log has a test fixture error: sorted first
Avatar was a peer with null rig pose; selecting the actual self row corrects
that negative test without changing adapter behavior.

`self_tests/test_ios_assets_removal_image_flow.py` is the separate normal
Marker-before-Model → prior PNG → ordinary Delete/Home → absent PNG → pure
owned replay → Marker cleanup composition. Its first bounded host run errors in1.649s during initial
Marker preparation: a duplicate fresh fixture `state` override accidentally
shadowed Marker inclusion and caused an entity-tree membership refusal. The
existing source guard correctly refused it. Combining the two fixture
projections fixes that test-producer mistake; the next full run remains
pending qualification. It uses original QML and staged Marker JavaScript with
explicit native/Qt/controller/parser/backend/GPU models. The new fresh removal
fixture selects one coherent host clock at birth,5000ms ahead of its unchanged
native producer, and derives tablet visibility from actual current controller
roots. A retained prior subject crop is only a proposed policy after Model
removal; it supplies no current bounds or measured pixels. No saved source is
retimed or rewritten. The larger outer300s harness covers this new two-image
composition; every existing operation budget remains unchanged.

The previous257-file removal timeout and the newly observed device52→36
historical-file identity refusal remain preserved in
[the Model dataflow checkpoint](ASSETS_MODEL_CREATION_ROUND.md). No opaque
marshal serialization experiment was adopted as adapter code: both measured
alternatives remained slower than the literal public-frame decoder.


The corrected normal run is terminal ERROR1/246.837s, not an outer timeout
(`assets-removal-images-owned-flow-second-20261027.log`). Its retained root is
`.ios-host-tmp/assets-removal-image-flow-8ty53izb`. The first actual PNG is
qualified, the original normal Delete is saved as `model-gone`, and Home plus
its original closing source finish with `contextClosedBy:5`. Thus the run
advances beyond the earlier120s prerequisite's unclosed context. It does not
complete the image join or Marker cleanup.

The next PNG stops at its original first GPU `inspect`, before any second
`read`: the inherited single-request test World reports `retired:true` from
the first request's proper release. The actual `FeatureCompletedFrames`
source maintains request-local retirement/holders with a shared instance and
sequence. Its guard correctly refuses the incorrect synthetic initial state;
no production GPU code or owner validation is changed. The failed second
sample remains `reading`, its GPU owner `opened`, and its exact inspect
receipt, empty opened PNG and all original responsibilities remain retained.

The fresh removal fixture now uses the existing Create/World Web per-request
pool pattern: old slots remain owned, service clock/sequence remain shared,
and a new request gets its own retirement state and an actual unique frame ID
when its first read begins. A new read still refuses another active or
undrained request. Two focused actual host transport cases verify these
boundaries, including old-holder refusal. With the six new image cases and
six old present-image cases, `assets-removal-images-gpu-final-first-20261027.log`
is terminal PASS14/1.063s. The complete new normal run remains unqualified
until a fresh bounded run reaches both image originals, the owned pure join
and unchanged Marker cleanup; no failed request is reused or repaired.

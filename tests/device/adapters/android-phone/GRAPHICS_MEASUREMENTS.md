# Phone original Graphics measurement join, version 2

`overte_phone_graphics_measurements.compose` validates original source packets
and derives actual v16 state. It accepts no verb, requested setting or expected
feature result. It performs no input, source acquisition, artifact writing or
cleanup and enables no capability. The complete Graphics adapter is still missing.

The owner supplies its current registered fixture run/ticket/root, pinned provider
birth and fresh read nonce, actual PID, original native before/after observations,
subject/view before/after observations, token-bound Graphics UI inventory,
independent passive Tablet inventory, original v2 world capture/PNG, actual clock,
phase barrier and external world-image policy. Each owning transport must enforce
its own nonce, context, source cursor and candidate/process guards. A future
durable source owner must preserve those floors across failed reads/recreation;
calling this pure join cannot establish transport provenance by itself.

Required acquisition order is native-before, subject-before, Graphics UI,
Tablet inventory, future recorded forward frame, original world capture,
subject-after and native-after. All original clocks must be fresh, after the
fixture phase barrier and span no more than 1500 ms. The actual native Test birth
must agree, before/after cursors must advance and graphics/lifecycle state must
stay unchanged across the capture. Original scene/entity inventories stay exact;
camera position tolerance is 1 mm, rotation components 0.0001, FOV 0.001 degrees
and aspect 0.0001. Quaternion sign equivalence is allowed without rewriting facts.
Old queued frame recordings cannot be retimed as post-barrier images. The actual
camera aspect must agree with the original target extent within 0.01.

Version 2 additionally requires trace version 2's immutable `recordedView` from
the actual RenderArgs frustum used when this forward frame was recorded. Its
original position, rotation, FOV and aspect must agree with the independently
observed native view. The original row-major projection and near/far geometry
must be finite, nonsingular perspective data. A later current Camera getter
cannot reconstruct or replace a missing/different recorded view, even when
image timestamps, batch counts and current marker cells are valid. Old trace-v1
packets cannot satisfy this full measurement contract. Native instrumentation
remains uncompiled; this is original command-generation view provenance, not a
claim that a GPU uniform/readback or final pixels were independently qualified.

Preparation checks require the original controlled HTTP scene ticket/receipt,
actual scene URL, all seven native UUIDs and their actual v2 positions, geometry,
names, colors, Zone haze, reflector mode and Web URL. Missing, renamed, moved,
foreign or stale subjects are rejected; HTTP success alone cannot prove readiness.
The declared controlled-subject scan must contain no foreign entities. The current
native view must match the fixed first-person fixture view. The scan's partial
property scope is not promoted into complete global foreign-state preservation.

The reviewed ordinary `View > First Person` action selects native `first person
look at` (MenuOption::FirstPersonLookAt). That original mode and native `first
person` are admitted only with the same measured fixture pose and recorded-view
agreement. A label/selection ACK cannot substitute for actual alignment.

Public `resolution/haze/mirror` come from original native preferences.
`renderScale` is the arithmetic mean of actual source-viewport/target ratios,
with anisotropy over 0.01 rejected; no rounding to the preference is permitted.
`hazePass/mirrorPass` report whether the original same-view trace contained the
corresponding executed draw-containing batches. They are deliberately independent
of preference flags. The join can therefore report a true setting with no pass,
or a pass despite a false setting; the common journey must reject that discrepancy
at its required checkpoints. These counters are not shader/fragment correctness
verdicts. `dialog` comes from the actual Phone Graphics page. Actual shown Tablet
ownership remains visible as `panel:graphics`, even if its current page is different.
Foreign Script managers/pickers and deferred picker requests prevent this join.

Every sample verifies exact original PNG/RGBA hashes and geometry, current
challenge cells, a disjoint nonblank subject ROI and world-target source. Fresh
transport digests cannot hide old/foreign marker pixels, a blank subject or a UI
screenshot. Returned evidence contains original hashes, native trace and measured
ratios. The existing common journey still independently checks change across
original subject images. Feature-specific pixel classification, durable
scene/settings/restart ownership, independent publisher and
complete native/host cleanup are still required before advertising a full triple.
No scene fixture or temporary image lease may be silently excluded from its
owning cleanup ledger merely because this pure function returns a panel list.

Twenty-two Phone host cases use explicitly synthetic original getter/socket/pixel
boundaries. Fixed synthetic pixels do not depend on requested feature flags.
Counterexamples cover settings without executed passes, passes despite false
settings, legacy/missing traces, validly hashed wrong markers, blank/UI images,
wrong scene/geometry/view, live mutation, lifecycle changes, old frame recordings,
context/cursor loss, missing inventories, stale/retired provider ownership,
anisotropy, mismatched projection aspect and a fresh image from a different
recorded view. These verify source-join logic only;
no native client, compiler, build, install or device was used.

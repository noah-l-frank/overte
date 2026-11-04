# Optional finalization after consumed cleanup

`Journey(..., after_cleanup_baseline=callback)` is an additive, in-process
test-system hook. The default remains `None`. It changes neither the v16
operation contract nor the public feature module's RPC routes or capabilities.
No public adapter currently receives this hook automatically.

The shared engine calls an explicitly supplied callback once, after both
ordinary cleanup calls and the unchanged three-second independent cleanup
baseline, before setting `cleanupSucceeded` and before publishing the report.
The enclosing module still closes its fixture after `execute()` returns or
raises. This gives an explicitly composed owner a place to finalize while its
original independent fixture is still available. A callback failure leaves
both success flags false. An earlier input failure remains the primary error.
The same hooked Journey cannot execute again after entering its finalizer.

The callback receives immutable UTF-8 JSON bytes with
`cleanupConsumptionVersion: 1`, the existing contract version, area, run,
fixture URL, current cleanup ticket and action barrier, `sequenceSucceeded`,
the actual final phase, only that cleanup window's actually consumed samples,
and the final primary sequence. It receives no expected-state recipe.
Decoding or changing a decoded copy cannot change the engine's original rows.
This is historical consumption, not a new source acquisition or a freshness
extension. The hook's return value is not a product release observation.

The wait pins its original phase and consumed sample bytes before returning.
The hook emitter refuses a caller-created window or a changed original window.
Its `sequenceSucceeded` is supplied only by the actual `execute()` path, never
by a caller argument. A direct invocation after a cleanup-only wait records
false; that narrow component proof cannot qualify a full external journey.

A feature finalizer must bind its exact warm source owners and compare these
consumed rows to their original observations and independently received actor
rows. It must preserve the existing phase/native-clock fences before further
input, verify actual release and archive originals, and close its independently
owned host handles. A callback invocation alone proves none of those effects.
A private second baseline cannot substitute for this external consumption.
The optional hook does not solve cross-RPC warm ownership, a durable global
observation cursor, stereo evidence, or native/device qualification.

Host checks are in `self_tests.test_feature_cleanup_consumption`. They execute
the actual shared engine against the independent input-reducing boundary model;
all product/native/network/device sources in that model remain explicit seams.

## Explicit Pico Audio cleanup polling

`audio_cleanup_poll_profile='pico-audio-cleanup1'` is an optional, in-process
selection on an Audio Journey. Its default is `None`. It cannot be combined
with the separate Browser `poll_work_inclusive` selection. The exact selected
object is retained and checked before another acquisition.

Only the `cleanup-restored-baseline` wait includes actual source and peer work
in a450ms polling period, with at least10ms real yield. Other Audio checkpoints
and all default callers keep the existing fixed250ms sleep. Both original
primary and independent samples receive final freshness checks after peer work;
an expired pair cannot qualify a window. The existing20s checkpoint, minimum
three advancing samples and3s cleanup window remain unchanged. The Pico Audio
source owner separately enforces its original500ms gaps and512/16MiB limits.

Seven host timing tests cover default behavior, the explicit cleanup period,
other checkpoints, source/peer deadline consumption, exact profile selection
and changed-selection refusal. The source work is a declared boundary model.
This selection does not compose the Audio adapter, authenticate an Actor,
retire resources, grant a public feature capability or qualify a device.

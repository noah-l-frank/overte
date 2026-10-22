# Original per-draw Pico stereo camera source

Feature 5/14 remains partial. The E2E-only backend seam associates the actual
original Batch and indexed command with its actual left/right camera bindings.
Only the immediately following executed lambda can acquire this source. The
executing backend, observed stereo frame and execution sequence must agree;
recording a batch, central head camera or completed unrelated draw is insufficient.

Doubled rendering observes each actual bound camera range and GL viewport before
its original GLES side call. Instanced rendering observes both bindings after its
original call. Neither publishes the single-draw source until the real draw
function has returned and exactly one left and right binding were acquired.
Missing, duplicate, unsupported or foreign bindings make the source unavailable.
The two cameras remain distinct from whole-batch aggregates. A reused aggregate
slot with changed original matrices or uniform values fails closed.

The actual execution-begin sequence is also the eventual completed batch's
sequence. Per-draw queries cannot guess a future sequence, reuse another batch,
read before/after the owned lambda, or borrow a prior model's missing eye.
The base backend returns false; unsupported backends supply no evidence.
Existing trace/capture versions and product render behavior are unchanged.

`tests/device/contracts/emote/test_draw_cameras_native.py` compiles the complete
original draw loop, GLES indexed command and camera readers in both doubled and
instanced configurations. It also compiles original camera structs, enum,
initialization and retirement fragments. Qt and GLM are real. GL calls/context,
Batch storage and transform storage are explicit host seams, so this verifies
source logic rather than actual GL, full translation units or device rendering.
Set OVERTE_TEST_GLM_INCLUDE to an existing reviewed GLM include directory; select
Qt5 with OVERTE_NATIVE_QT_MAJOR=5 and OVERTE_QT5_HOST_ROOT when appropriate.

Original model payload identity, host model-specific per-eye validation, captured
PNG/submission joining, independent actor publication and whole cleanup remain
unfinished. No complete Emote capability or public model-draw result is enabled.


## Loaded model and submitted capture join

The original loaded Model/Geometry identities and original HFM URL SHA are
captured in the actual mesh payload constructor. The weak original draw mesh
also distinguishes normal runtime mesh replacement. After the real indexed
command, immutable world bounds, index count and actual deformation bits enter
its immediately following lambda. Model/Geometry ownership never escapes it.
Only normal primary stereo rendering contributes, excluding mirror/shadow views.
The metadata fragment is selected from fixed committed Phone source f84dd87eb66f;
its mono trace/adapter was not copied or relabelled.

FeatureRenderTrace now validates every actual per-draw camera against the
completed original batch's camera rows, including matrices, uniform viewport,
stereo information, actual GL viewport, eye, slot, sequence and draw counts.
Duplicate draw claims, changed source identity, unmatched cameras and bounds
retain no usable model source. The separate pico-model-draw-trace v1 table is
bounded at 128 models, 4096 commands and 512 model/camera references. Each model
retains its actual per-eye cameraUses counts. Whole-scene forward views cannot
supply another model's missing eye. Existing Graphics trace v4 stays unchanged.

FeatureWorldRender retains that table with its pending original PNG and publishes
it only when the same actual frame is successfully submitted through the existing
OpenXR path. The closed feature-pico-world-model-draws-observe request selects
only an already owned capture nonce. It cannot start an acquisition, request a
model, alter a camera or establish visibility. The pico-model-draw-capture v1
packet retains original capture/acquisition sequences, GPU time, PNG/pixel hashes
and native frame/execution identity. Model-source failure leaves the existing
Graphics image available. Capture release/expiry clears model maps with the PNG;
late callbacks cannot recreate retired capture evidence. This adds no GPU object,
QObject, input callback or independent resource lease.

The private _emote_model_draws_observer uses the same installed candidate, actual
PID, native transport and final native clock guards as the shared avatar reader.
Its probe forwards the original once to the existing mode0600 private writer.
Host validation requires trace/capture v4 and successful original submission,
exact image identity and model-specific camera counts across all rows. The
avatar_draws join additionally brackets the capture with original loaded model,
geometry/source, Rig, pose and central recorded view. The central projection is
never used as an eye camera, and drawn bounds are not a visibility verdict.

The expanded focused native check compiles entire original FeatureRenderTrace
and FeatureWorldRender classes, the full TSI getter, original mesh identity/render
fragments and drawCall, plus the original backend/GLES functions above. Qt PNG
encoding, locks, timers and GLM are real; GL/Batch/transform state, loaded geometry
and surrounding application/context services remain explicit seams. It proves
pending/wrong-frame/unavailable-model/cancelled-callback behavior in both stereo
configurations, including image availability when model provenance fails.
Full native translation units, actual GL/OpenXR, application/APK and devices are
still unqualified. Host original geometry/camera/image/candidate counterexamples
belong to emote-original-sources and normal-emote.

The next packet must measure current challenge pixels and meaningful original
avatar body changes in each eye using only that model's actual cameras, retain
original captures through owned release, and compose the independent actor and
whole normal-input/resource flow. No complete Emote capability is enabled.

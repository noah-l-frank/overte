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

# Original Pico Emote stereo pixel measurements

Feature 5/14 remains partial. emote_pixels.py measures the unchanged original
submitted PNG in both eyes using the model/geometry/Rig and executed camera join
from [model draw provenance](EMOTE_DRAW_CAMERAS.md). Each model-specific camera
projects all eight original world-bound corners into that eye. Unsupported,
clipped or ambiguous projections fail rather than borrowing another scene view,
central/Phone frustum or a convenient camera slot. The fully projected body must
be at least 24x48 original pixels in each eye. The separate fixed external
pico-emote-pixel-policy v1 contains each eye's marker and subject rectangles;
each must lie inside its actual original target viewport. The subject must cover
the projected body and occupy at most twice its area.

The existing common original-PNG/challenge decoder checks the current run/ticket
in each eye independently. The PNG and pixel hashes remain original capture
hashes. No derived crop, duplicated eye, resized image or new artifact is supplied
as source evidence. The common verifier may internally sample its original ROI;
the body/control measurement directly samples original pixel coordinates.

A comparison keeps the previous original frame/PNG at its original source time.
It requires a new capture, acquisition, GPU frame/execution, submission and native
avatar cursor, unchanged loaded model/geometry/Rig/root pose and source extents.
Actual camera changes are bounded and retained: maximum view/projection element
changes are reported separately for each eye, limited to .002. No fixed Phone
head pose or reconstructed eye projection replaces the actual headset cameras.
A larger motion needs another original pair and cannot pass this measurement.

Both eyes independently require at least 5% changed body samples and at most 1%
changed control samples. Each body/control set contains 1024..65536 original
samples, with explicit stride. Control sampling stays in that eye and excludes
the body and changing challenge margins. These are bounding-region measurements,
not shaded-fragment masks or an animation verdict. Original advancing Rig/clip,
normal input causality, controlled scene/material/avatar identity and independent
actor evidence must join separately before any feature state is published.

Final copy, candidate checks and repeated original PNG/source validation remain
inside the five-second operation budget and original 1500ms native age window.
A frozen native clock cannot hide host time spent decoding/revalidating, and a
frozen host clock cannot hide a final native clock jump. Historical comparison
bytes are never retimed or returned as a current acquisition.

Ten synthetic original PNG/camera counterexamples cover correct two-eye body
changes, ignored/one-eye-only changes, moving background, stale/foreign challenge,
wrong original image, wide/swapped policies, unrelated forward cameras, replaced
geometry, reused GPU frames, measured small late poses and final guards/clocks.
The original Phone bounded stride/body-versus-control approach is reused from
fixed committed source; mono projection and Phone scene/input owners are excluded.
These tests execute no renderer, HMD, GL/OpenXR device or target automation.

Next: bind durable acquisition/archive/native release, actual normal Pico
scene/avatar/view setup and the existing original Rig effects, then independent
actor/public coordination and full callback/resource retirement. A first-person
view whose full body bounds cannot project is ineligible; no camera/property
setter or fabricated body ROI is used to force a pass. No full Emote capability
is added by this internal measurement component.

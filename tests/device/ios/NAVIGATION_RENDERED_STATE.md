# iOS navigation rendered-state prerequisite

`navigation_world_measurements.compose` validates existing original native
navigation-before/after packets, one original Vulkan capture and its actual
retirement proof. A separate `NativeClockAcquisition` join binds their immutable
digest to the measured native/host window. It does not acquire SDK sessions,
change camera/scene state, recapture pixels, retime a cached image or advertise
the Worlds/navigation triple.

The owner supplies the exact durable capture command, run and installed-code
binding. The join requires the bound PID, unchanged lifecycle, both original
navigation source births/sequences, current committed scene history, settled
actual avatar state and identical scene properties. Actual native acquisition
ordering must surround recording, submission, fence completion, pixel readback
and actual resource retirement. UTC and elapsed progress between the navigation
reads must also agree. A new digest around earlier capture times is insufficient.

The original GPU trace must contain actual issued forward draws. Its recorded
camera must match both live native camera reads, including position,
orientation, FOV, aspect and perspective. The original pre-HUD Vulkan RGBA PNG
and decoded pixels must match the native byte/pixel hashes and dimensions.
An acknowledgment of release cannot replace actual zero callbacks, GPU work,
metadata, PNG storage and GPU allocation in the same capture source/request.

`controlled-purple-wall-v1` projects fifteen points on the measured controlled
scene's collision-wall front face through the original numeric GPU matrix.
Only in-frustum patches with adequate image margins count. At least six distinct
visible patches and 80% qualifying patches are required; each qualifying patch
must have at least 80% purple pixels under the fixed conservative chroma rule.
Unknown lighting, occlusion, offscreen geometry or an unsuitable viewport fails
rather than substituting a guessed screen rectangle. This fixture-specific
pixel profile remains physically unqualified. It is not a general scene-color
calibration or a generic screenshot similarity assertion.

The version-1 rendered-state result preserves the original image/pixel hashes,
frame ID, scene generation, installed binding, native epoch, actual host window
start and measured pixel patches. It does not constitute the shared journey's
`image`/`changed` evidence: the per-ticket visible challenge marker, canonical
subject-change measurement and independent publisher are still required. The
static base fixture has no such marker. The optional [normal navigation
scene](NAVIGATION_SCENE.md) supplies it, and [challenge-image validation](NAVIGATION_CHALLENGE.md)
now independently decodes it. Server delivery must not manufacture image facts. The future whole-operation owner must supply that actual
visible source through the normal scene/UI path and retain the originals with
Worlds-specific ownership records. The Graphics archive filename convention is
not repurposed here.

Host tests decode real PNG bytes and exercise real pure validators against
synthetic native/GPU boundaries. Counterexamples cover blank/wrong pixels,
foreign/truncated PNGs, wrong cameras/backends/stages, zero actual draws,
reloads/motion/lifecycle changes, retained callbacks/GPU allocations, native
clock disagreement and foreign process/request bindings. Native compilation,
actual rendering and device execution remain unperformed by instruction.

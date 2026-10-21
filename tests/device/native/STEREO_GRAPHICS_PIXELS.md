# Original stereo Graphics geometry and pixels

The opt-in `stereo-graphics-pixels` v1 reducer takes an original world-render v4
packet/PNG and separate fresh native subject snapshots around its acquisition.
It delivers no input and advertises no complete feature capability. Native
preferences, page/fixture ownership, actor publication, lifecycle durability,
resource retirement and full feature coordination remain separate obligations.

The actual original capture request, full encoded PNG and pixel hashes,
executing Frame/execution and subject birth/request/cursors survive reduction.
Both subject reads must belong to the original run/PID and immutable scene
resource; all seven UUIDs must be present and their original properties stable
around acquisition. This does not infer preservation of foreign scene entities
from the bounded scan or from fixture setup.

## Actual two-eye geometry

Column-major view/projection matrices come from the actual bound GPU cameras,
including late HMD correction and projection jitter. Their original viewports
map through the captured source subregion to the complete tone-mapped target.
Doubled driver viewports and instanced split-screen shaders both map a full eye
projection to the corresponding original half viewport. GL-to-top-left pixel
conversion keeps the complete source image. No crop, duplicate, resizing,
re-encoding, CPU-camera reconstruction or image alignment is returned as proof.

Every distinct original camera in the relevant executing batches participates.
The reducer cannot select a convenient camera slot. It decodes each of the 128
marker cells at the projected original world Web plane in both eyes, requiring
adequate original cell spacing, finite in-eye projections and the exact current
challenge in every candidate. The card's actual 160x40 layout and 128x32 inner
cell region are preserved. The reported challenge digest is derived from the
decoded pixels, rather than filled from the requested challenge. Missing,
ambiguous, stale, offscreen and undersized cards fail.

Haze-board regions use the original Forward cameras. The reflector region uses
the original root Mirror draw's saved cameras when such draws executed. Only a
trace with zero Mirror draws uses Forward geometry for the original no-mirror
region; this distinction is explicit in the result. A Mirror render-target
camera is not substituted for the actual final rectangle's camera.

The inner target face is projected from the independently read entity geometry.
Only original pixels inside every candidate polygon and outside every original
marker polygon contribute. Results retain each eye's target UUID, conservative
ROI/polygons, pixel count, RGB means, blue dominance, orange fraction and coarse
RGB histogram. These are photometry, not preference values or a verdict that a
setting took effect. A full coordinator must compare these originals across
source-bound preference transitions, preserving unrelated settings and scene
state, and require the common original image/actor evidence as well.

## Budgets and verification

Processing has a five-second monotonic ceiling with bounded image/source sizes
and periodic checks. Final original native time, candidate/process guard and the
1.5-second oldest-source freshness bound are checked again. A frozen native
clock cannot conceal slow host processing. Pixel bounds conservatively floor or
ceil without expanding regions to make an idealized fixture pass.

Host tests paint analytical rectangles independently of the projection reducer.
They cover both GPU techniques, actual late views and distinct Forward/Mirror
cameras, both-eye challenge decoding, original full-image identity, copied/black
right eyes, stale challenges, ambiguous cameras, foreign/changed sources,
undersized/offscreen cards, late guard/clock loss and slow processing. These are
synthetic source/pixel checks. Native compilation, actual Web texture orientation,
real geometry visibility and physical HMD output remain unqualified; no compiler
or device was used.

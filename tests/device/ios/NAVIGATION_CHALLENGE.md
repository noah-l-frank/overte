# iOS original navigation challenge images

`navigation_challenge.evaluate` validates already acquired original inputs; it
creates no SDK session, input, capture or fresh evidence envelope. Its source
record contains the original navigation/GPU/retirement/clock-join frame, PNG
bytes, exact durable capture command, run/ticket, actual scene-provider snapshot
and resource root. The feature owner must acquire and retain these originals
under the installed-code/process/role/file ownership boundary.

Native navigation state writer version 2 passively queries the actual run's
marker UUIDv5. It records original presence, type/name, entity host, source URL,
spatial properties, visibility/collision state and last-edit time. Version-1
state remains readable for historical/base scene prerequisites; it cannot fill
marker-image evidence. Both sides of a frame must preserve the actual marker
metadata, source identity and the other scene/pose/camera/lifetime conditions of
the [rendered-state prerequisite](NAVIGATION_RENDERED_STATE.md).

The actual marker must be a visible local/domain Web entity matching the
versioned controlled scene. Its observed source URL selects its original scene
load ticket and resource root. The original scene provider must retain the
corresponding exact byte/hash receipt and current run/ticket. The marker page
can survive later tickets while polling `/current`: its original source URL is
not relabeled as each new step's ticket. Input delivery is independently checked
but cannot substitute for visible pixels.

The original GPU recorded projection and measured entity pose locate the four
card corners. This profile supports the normal aligned controlled viewpoints;
tilted, clipped or offscreen cards fail. The ROI covers only the actual card's
128-bit interior, using its versioned PNG coordinates. It must project to at
least 128 by 32 pixels. No expected screen position is returned as an observation.
The measured front-wall floor boundary locates a separate subject ROI. The shared
`image_observation` decoder must find the exact current run/ticket in the original
PNG and a nonuniform scene subject outside the marker.

For `changed`, the caller supplies the complete previous original sample. It is
validated historically with its own unchanged clock join and image hashes.
Tickets, capture requests, frame IDs, source sequences and acquisition windows
must be distinct and ordered, while the installed binding, source births,
immutable native scene history and provider receipt history must continue.
The shared image comparison requires at least 5% changed subject pixels; changing
only the marker cannot satisfy it. The canonical B-to-A bookmark visit and its
opposite A-to-B example are both covered by host counterfactuals.

The version-1 challenge result preserves the original record hash, actual image
hash/change fraction, derived image policy and original rendered-state result.
It does not publish a whole-area capability, independent peer result, durable
ownership or cleanup completion. Native Web document/texture callbacks, source
restoration, restart, three-second quiet windows, repeated cleanup and paired
process/SDK retirement still belong to the pending full Worlds owner.

Host tests use real PNG decoding and comparison with modeled native/GPU/DOM
boundaries. They reject old/foreign tickets, marker-only changes, missing or
foreign marker sources, absent/wrong host/type/geometry, changes during capture,
source downgrade, receipt loss, source-history changes and reused frame/process
cursors. No native compilation, actual Web rendering or device qualification was
performed. Fixed lighting/viewport/projection assumptions remain physically
unqualified and fail closed when unsupported.

# Owned Pico world-surface stimulus v1

Graphics resource status v2 adds the explicit `pico-stereo-cues-v1` profile.
The fixture reader selects it with `Client.register('graphics',
graphics_profile='pico-stereo-cues-v1')`; an adapter cannot change that profile.
Default registration still produces the exact legacy v1 status and seven-entity
scene. The readiness envelope remains v1. Readers retain both status versions,
pin the selected profile and preserve append-only original socket receipts.

The Pico variant uses the same seven entity IDs. Its far Haze board and reflected
color subject are world Web surfaces, each polling the existing owned `/current`
route for an immutable ticket PNG. The PNG carries a surface-specific 128-bit
challenge, four-byte magic and CRC32, plus two calibration columns per row.
The Haze board has black/white cells; reflection has dark/orange cells. The
reflected surface faces the actual mirror. The variant sets the Zone Haze range
to 90 meters so far-board cells retain nominal contrast; the legacy range
remains 18 meters. This arithmetic is stimulus design, not a shader verdict. The near black/white marker remains
unchanged. No page calls a product bridge, changes Graphics settings or reports
observations. Late image callbacks cannot replace a newer ticket image.

HTTP delivery establishes stimulus delivery only. This packet does not decode
a headset image, prove visibility through the actual VR tablet, measure Haze or
reflection, or advertise a complete Graphics capability. The current original
image verifier v1 continues to reject a shown tablet. A separately versioned
verifier must decode both original eyes with actual executing GPU cameras,
qualify the original UI composition, and join the native observations and exact
fixture resource hashes before open-page checkpoints can pass.

Retirement keeps historical profile, activation and original response identity;
new world resource requests fail. Old ticket PNGs remain immutable while the run
is active, and their delivery is recorded under their original ticket alongside
the actual current ticket. They cannot be relabelled as fresh evidence.

The registered no-build stereo group includes deterministic codec, original
loopback HTTP, version compatibility and actual page-script counterexamples.
Browser/GPU/native execution and devices remain unqualified. Reconcile these
shared fixture additions with Phone explicitly; its default profile is unchanged.

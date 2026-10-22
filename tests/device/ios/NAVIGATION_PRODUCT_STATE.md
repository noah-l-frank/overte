# One original eight-field Worlds state

`navigation_product_state.compose` joins all eight shared Worlds fields from
unchanged originals: rendered location, bookmark presence/name, search query,
owned result IDs, error, Places panel and Go To visibility. This is a private
pure composition component. It does not publish peer evidence, own user input,
enforce cross-sample durable cursors, implement restart or retire resources.
Worlds remains partial and no full capability is advertised.

The caller acquires one bounded outer `NativeClockAcquisition`. Originals are
the actual bookmark, Places model, normal UI, Places HTTP, native dialogs,
navigation replies, four original world-image packets and a final navigation
state packet. Its original digest covers every packet. Source times retain the
actual top-level UI/reply/capture/retirement times. Existing source validators
check their own nested clocks; the field projections additionally join those
read intervals to the outer native interval. The whole envelope remains below
the existing 1.5-second host acquisition limit. An actor's actual transport must
meet that limit; modeled host tests do not qualify physical timing.

The original owned image archive supplies the unmodified PNG bytes and original
challenge sample. `navigation_challenge.evaluate` independently checks actual
GPU completion/lifetime, original pixel hashes, real committed scene/grounded
pose, actual native marker geometry/source, current decoded ticket and visible
wall effects. A/B comes from that validated actual state, not an expected step.
The image's scene URL, fixture root and provider instance must match the attached
original input context. Directory and missing proofs must belong to that same
original provider instance and installed candidate.

The inner image acquisition must be contained in the outer interval in both
original native sequence/UTC and measured host UTC/monotonic domains. Original
native observer birth and lifecycle must agree. The four actual image packets
must equal the packets hashed by the outer acquisition. An old image cannot
borrow a new outer timestamp or a different capture packet.

The final original navigation read must follow every other source read. It must
preserve actual scene generation/history, marker geometry/source, domain, view
and settled pose from the image's final navigation packet. A changed scene,
camera, FOV, actual position or missing marker prevents a coherent observation.

Places and error projections consume the same original UI packet. Two
deterministic validation views select their original packets from the full
envelope. Only the selected-original digest and source-time list differ from
the full clock join. Every original native packet, native timestamp and host
acquisition boundary stays unchanged. These views are metadata derivations,
not new source reads or newly minted freshness. The full original clock-join
hash remains in the product-state record.

The [Places projection](NAVIGATION_PLACES_STATE.md) supplies actual saved/loaded
bookmarks and current selected model/editor/UI facts while preserving a genuine
old directory-consumption proof without retiming it. The
[error projection](NAVIGATION_ERROR_STATE.md) preserves the missing lookup's
original ticket while fresh native modal/listener lifetime establishes dismissal.
Both must agree on the same actual Go To inventory. The final eight-field state
also passes the unchanged shared public vocabulary/privacy validator.

`iosNavigationProductStateVersion: 1` retains binding, run/current image ticket,
full original and clock-join hashes, the underlying image/Places/error results,
original native interval and measured host acquisition start. Repeating historical
composition returns the same historical result. It cannot claim another current
read, advance an actor sequence or retire image ownership. The final owner must
still validate original file ownership, phase consistency, source cursors,
independent actor publication, changed-image selection, restart and repeated
resource/quiet cleanup.

Host tests construct coherent native/UI/GPU SDK source packets, execute actual
Places JS/QML processing and filtering, use real temporary bookmark bytes and
decode original PNG challenge pixels. They cover initial/current B states,
matching errors and dismissal, mixed/reused image packets, bad nested clocks,
changed current scene/view/pose, wrong fixture/candidate, missing actual sources
and unmodified historical clocks. Native code is uncompiled, all device behavior
is untested, and this packet does not establish device acceptance.

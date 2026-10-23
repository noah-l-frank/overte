# Android Phone final manual-session review, 2026-10-23

This review records the pre-integration boundary. The subsequent authorized
[combined-source campaign](INTEGRATED_CAMPAIGN.md) tracks product integration,
matching build and actual Jenkins results separately.

This is the second read-only review of the completed Android Phone manual-parity session. It continues the first [adapter review](PARITY_FINDINGS_REVIEW.md) from `d75486b78a4d7f5e4fa5fca2ba7f75f1e4e7f8cd`. Source inspection and local host checks do not convert manual results into automated acceptance. The other session's worktree, reports, installed packages and device reservations were not modified.

## Changes since the first review

All 200 source hashes declared by the final P119 local source plan matched the final worktree in stable reads. Of the same 441 selected script/probe entries inspected before, only `scripts/system/snapshot.js` changed since that inspection. P117 declares Snapshot Copy URL changes; P118 changes WebFramePixels and its host counter; P119 changes WebTextureRenderer. This review checks local source/plan consistency, not installed APK identity or the other session's historical measurements.

| Final change | Effect on the existing adapter work | Required handling |
| --- | --- | --- |
| Snapshot Copy URL and retained animated URL | `snapshot.js` now reads, writes and clears `previousAnimatedSnapUrl`. This is touched even by ordinary capture/reset paths. The old native/Python fixed settings scope omitted it, so otherwise successful cleanup could leave it outside restoration. | Both fixed scopes use private settings-lease v2 and reject v1/missing-key/incomplete restoration evidence. Preserve original presence, typed values, exact serialization and owner continuity. Validate archived captures before new input, including captures whose index-save was interrupted. |
| Snapshot normal Copy URL input | A new `snapshotCopyUrl` control and `copySnapshotUrl` message copy the actual uploaded URL and remove its story from auto-delete candidates. | No existing public DTO requires reinterpretation. Automated Copy URL coverage remains missing: use the normal button, independently read the real clipboard, compare downloaded bytes with the original file, test retention after a second capture and perform exact owned cleanup. A script message or copied expected URL is insufficient. |
| World Web pixel-pack fix | Four-byte pixels now use bulk row conversion with explicit byte order and a fallback for other layouts. The existing bottom-up RGBA to premultiplied BGRA output contract remains intact. | No new adapter DTO or pixel interpretation is required. Preserve original pixels, image freshness, owner/document/source identity and independent text/image checks. Do not compensate with weaker pixel thresholds or synthetic expected frames. |
| Presentation pause/resume lifecycle | Pause dismisses the Presentation and detaches its surface while retaining the document/display; resume recreates the visual window. Final close releases retained resources. | Existing observers track retained native/Java owners, not Presentation existence, so paused absence is inactive/not-ready and cannot prove retirement. No wire change was found. The full ordinary retained-document frozen/picker/owner-return workflow remains separate automated coverage. |

## Existing findings remain bound to their sources

The earlier People REST fixture correction and domain-owner preflight remain applicable. The final live Avatar, Create, People and Places script hashes match those recorded in the first review. The other session's account-label product fix is present in its source and is reported manually checked. It is absent from this test-only source baseline; its six genuine QML regression failures must not be relabeled as a pass.

The final live probe is unchanged from the older foreign baseline, and its Snapshot script still needs reconciliation with our capture-event instrumentation. Product fixes and required E2E hooks must be joined together before reviewing exact executable admission pins. No automatic repin, imported functional product change, public v18 expansion or blanket compatibility claim is made here.

## Private settings-lease transition

Lease v2 requires fourteen fixed keys, including `previousAnimatedSnapUrl`.
The command schema stays at v1 and common feature contract stays at v18.
Native v1 responses and archived v1 captures remain invalid for v2 even if a
producer adds the new field. Existing v1 journals retain their ownership and
original bytes; finish them with their matching old instrumentation instead of
silently migrating, overwriting or deleting them. The extended owner validates
archived captures before choosing UI/native factories or saving new action
state, including a capture retained before its `settingsIndex` save completed.

The normal Copy URL control, clipboard readback and downloadable-file retention
scenario are not implemented by this lease change. Its purpose is complete
restoration of a newly touched setting, not a claim of new feature acceptance.

## Manual evidence and automated coverage

The final 18:11 UTC checkpoint reports scoped P118 Copy URL/Redo and P119 frozen/picker/owner-return passes. Those reports improve product evidence for those exact packages and cases; they are not runs of these adapters. The checkpoint explicitly retains Audio C as partial, historical hangs without universal causal resolution, and broader lifecycle limits. No real-target acceptance registry or fourteen-area source/host status is promoted from those reports.

The existing image oracle decodes the current run/ticket challenge from actual
PNG pixels, so an old whole frame from another phase is already rejected. No
current resume-image bypass was demonstrated. The narrower remaining gap is
correct current marker/DOM with stale visible text or subject pixels. Ordinary
typing phases lack a final glyph assertion. Current resume recreates the
document, so it does not test P119's retained-document lifecycle. A later bounded
extension needs a real delivered producer epoch/serial tied to
owner/grant/page/surface and a post-resume barrier, plus independent visible
content checks. Neither a fresh screenshot timestamp nor a producer serial
alone proves displayed text correctness. Normal API34 IME replacement and real
outstanding-picker return remain distinct automation gaps.

## Verification at review completion

- Settings reader/transport module: **14/14 PASS**, 0.042 seconds unittest.
- Four selected extended-owner recovery/negative tests: **4/4 PASS**, 15.147
  seconds unittest; the 1,310 selected receiving inputs remained unchanged.
- Existing small Qt6 settings component: **PASS**, including actual typed
  original presence/value, omitted scope and incomplete-URL restoration. This
  compiles original SettingsManager/Handle/Snapshot bodies with documented host
  seams; it is not a complete Android build.
- Both settings component runs retained fourteen selected input hashes and
  empty own process groups. The receiving six-file package matches those
  tested bytes. The complete Snapshot wholes and old QML campaign were not
  rerun or relabeled by this review.

At review completion no APK, installation, hardware operation, Jenkins run,
push or PR had been performed. A subsequently authorized combined-source
integration and Jenkins campaign must record their own source identities,
build/install bindings and individual results separately.

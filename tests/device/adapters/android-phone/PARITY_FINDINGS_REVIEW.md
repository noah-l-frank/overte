# Android Phone manual-parity findings: adapter review

This first review is historical. See the subsequent
[final session delta review](FINAL_SESSION_REVIEW.md) for the new Snapshot
Copy URL setting, pixel-pack and Presentation changes and private lease v2.

This review starts at `a7be274da152b9d0b77e2fe5bb9874c5b1e18a31` in an isolated local worktree. The previous source/host adapter baseline and the ongoing manual-parity session were not modified by this review. No APK, native build, installation, hardware test, Jenkins operation or remote write was performed.

## Result and integration boundary

The comparison found a real test-fixture protocol error, a missing QML regression, and an infrastructure readiness gap. The changes below correct test infrastructure and add regression coverage. They do not import functional product fixes or qualify the other session's live source. The previous fourteen-area source/scoped-host matrix remains historical evidence for its exact source and synthetic boundaries, not a pass of this review branch or of a new product build.

| Area | Change or finding | Remaining obligation |
| --- | --- | --- |
| Avatar / People | Controlled service requires wrapped JSON POST for initial requests and polls, returns the actual Iamus data envelope, rejects successful-GET evidence, and checks actual reciprocal responses. Existing negative tests cover ignored peer requests, missing results, failed pending and conflicting nested/flat results. | Pinned product `peopleConnection.js` still uses the incompatible poll/response handling. Review and integrate the separate product fix, then reconcile exact executable pins and test actual product consumption. A green synthetic producer does not repair it. |
| World Navigation | An owned domain receives a fresh idempotent online preflight before input. The owner verifies live children and current domain identity. Invalid, unavailable or foreign owners block navigation as infrastructure errors. | Client arrival, identity, grounded feet, world rendering and hardware acceptance retain their existing independent obligations. The fixture already uses y=0; a foreign lab's raised address is not a new adapter defect. |
| Authentication | The existing WindowRoot host contract now tests initial Account binding, profile/logout changes and username shortening. | Six new cases fail on the unchanged product. The isolated two-property product-fix countercheck passes, but that fix is not integrated here. The visible TabletHome header still needs independent passive E2E observation; see [Authentication](AUTHENTICATION_FEATURE.md#tablet-account-header-coverage-boundary). |
| World Web / Lifecycle Input | Existing typing/clearing and image freshness do not prove final visible text after Paste/Undo/Redo. Direct WebView commit does not exercise Qt's API34 native replacement path. | Add a reviewed normal-input regression with independent DOM/cursor and final editor-pixel evidence, including correct-DOM/stale-pixels negatives. Retain the other session's native replacement tests when product sources are joined. No new wire contract is justified solely by this inspection. |
| Tablet Web | Held inline callback ownership is distinct from a real outstanding file-picker lease. | Preserve relevant existing production picker/source-owner component regressions during product integration. Do not infer physical picker acceptance from current synthetic cases. |

## Source reconciliation

The read-only comparison inspected 441 selected source entries and found eight different paths, with no missing or unstable reads. Six are new working changes relative to the other session's own HEAD: wearable local dimensions, Create null-UUID unparenting, selection-error clearing, touch/coarse voxel picking, People REST handling, and the immutable portal script URL. Snapshot and probe are byte-identical to that session's older HEAD; their missing instrumentation is a historical baseline difference, not a new removal by that session.

At the later product join, retain or strengthen the existing production counters:

- Avatar entity getters must honor requested properties, then prove local dimensions survive actual wearable notifications at different avatar scales. The current native adapter already requires local dimensions.
- Create must check native null-UUID semantics for unparent/undo, clear stale errors after valid refreshed selection, and reject ignored, unauthorized, multitouch or unreleased voxel gestures. The common populated-volume removal/undo scenario remains valid; empty-volume touch-add is additional coverage still needed.
- Places must retain portal consent and actual arrival evidence when checking the immutable `qrc:///scripts/system/places/portal.js` origin. The URL alone proves no navigation result.

The live Snapshot and probe files lack parts of this adapter branch's E2E instrumentation; replacing them wholesale would discard required capture timelines, closed Phone dispatch and uncached command observations. No source-admission pin is regenerated or relaxed here. Nonmatching product sources must remain inadmissible until a reviewed source/instrumentation join.

## Verification and handoff

The receiving worktree's actual checks passed: People service **17/17** in
9.190 seconds, domain fixture/session **15/15** in 33.933 seconds, and the complete
Avatar composition module **10/10** in 83.366 seconds. All 1,550 selected input
hashes remained stable, with no timeout and empty own process groups. These are
test-logic, loopback-service and synthetic Phone measurements; the Avatar module
does not execute the product People JavaScript.

The focused QML account regression measured **11 PASS / 6 FAIL** on unchanged
product source. An external a7 snapshot with only the two account-property fixes
measured **17/17 PASS**. That countercheck proves regression specificity, not a
pass of this branch or of a product build. The QML regression remains a genuine
failure until its separate product dependency is integrated; no XFAIL, skip or
expected-value echo turns it green.

The receiving worktree's complete existing QML runner measured **42 PASS /
6 FAIL / 0 SKIP**, with exactly those six account cases and no unrelated
failure. Its 954 selected inputs and two runner files remained stable; the
process group was empty after completion. The aggregate QML result stays RED.

The local final review manifest records raw logs, exact commands and SHA-256
bindings. Its directory is
`/home/user/Documents/github/overte-phone-parity-adapter-review-20261023-report`.

Before product qualification: join the separately owned product fixes without losing instrumentation, reconcile exact source identities, make the real QML regression pass, and implement the documented observation/input gaps. Then run authorized version-bound native/device acceptance through the prescribed laboratory. All fourteen areas remain unverified on physical clients in this review. Pico and iOS receive no qualification from Android Phone results.

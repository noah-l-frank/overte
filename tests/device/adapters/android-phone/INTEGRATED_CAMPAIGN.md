# Android Phone combined-source integration and sequential campaign

The user authorized integration of the completed manual-parity fixes with the
Android Phone adapter work, a complete matching E2E APK where required, and a
Jenkins campaign that records every individual result and continues after a
failed test. Only the Proxmox laboratory may execute hardware tests.

## Source integration

The isolated branch is `test/android-phone/integrated-parity-adapters-20261023`.
Merge `a434c7f8ce` joins review `0b7a62d637` with the exact final 200-file manual
source snapshot `2f081e02f10e138e309ef70c2a2528977c84ce1d`, whose parent/common
ancestor is `f46c4e399ed0227cfba4ae3a0d4d29a91dedc6ce`. The original manual and
completed adapter worktrees remain untouched. The snapshot was validated against
the final P119 source plan before creating its local Git tree.

Eleven overlapping conflicts were resolved by retaining product behavior and
E2E instrumentation. Duplicate domain readiness and account tests keep the
stricter existing adapter checks. The Noto Emoji license text retains its
content, with whitespace normalized to repository line endings. Web integration
also preserves the Qt recipe/export/lock, cursor/IME and packaging dependencies;
41 reviewed Web paths match their planned three-way result.

Post-merge compatibility work preserves actual submitted-source-before-compile
ordering, native Script UI identity and full failed-URL causality. Private
Snapshot settings lease v2 includes all fourteen keys, including the newly
written `previousAnimatedSnapUrl`, and rejects unsupported archived captures
before new input. No observed source hash is automatically learned as approved.

## Campaign boundary

The current catalog contains 69 distinct modules: 58 in `feature-journeys`
(14 mandatory capability gates, 14 journeys and 30 foundations/core modules)
and eleven other catalog modules. The supervisor must attempt targets serially,
retain one target result per module, record necessary setup separately and
continue to later targets after an assertion, infrastructure error or missing
summary. It must preserve actual reservation, installed-artifact, prerequisite,
timeout, cleanup and privacy checks. Missing required capabilities are errors,
not green skips; a missing independent Phone actor cannot be simulated.

The legacy live Phone job uses older fixed sources and is not repurposed.
The task-owned job is `overte-phone-integrated-campaign-20261023`, retaining the
actual Phone/voice resource locks. It receives a frozen source archive, full
debug feature-ON APK, build/install receipts, catalog inventory and supervisor
through the official CLI, with independent chunk/full hashes. No historical
workstation installation receipt substitutes for a fresh installed-code check.

The complete APK uses the existing verified 16 KiB dependency lineage, fresh
application native outputs, private copied metadata/Gradle/signing state and
read-only historical artifacts. The complete product build is distinct from
the earlier partial host component checks. Actual combined-build and campaign
results follow; earlier host evidence retains its original revisions.


## Actual combined build and Jenkins result, 2026-10-24

The frozen tested source is `0a7de4299f4bb97e99c844288e6381efd973df0f`.
The matching full debug E2E APK has version code **15** and SHA-256
`43ed8f0ad7e9e5fe4beaa7c39833441f42979ff209181eaf00e4ec933df41248`;
its source archive SHA-256 is
`e7a5f43d503eb5cf9e0503e9a35579e270e0892c35ace3370b969c746b79b6ea`.
Actual native compilation, native/resource/Probe/Dex provenance and installed
identity were verified. Incremental dependency provenance is preserved; source
store archives were not reverified or relabeled as a new cold build.

The frozen campaign manifest SHA-256 is
`109d95a40539b3f625acd0ca9828b9fa4c2020925bd2062bb0c9b4ed674ac3b8`.
Jenkins build **3** completed **RED: 7 PASS, 5 FAIL, 57 ERROR**, with no aggregate
skips. Earlier builds 1/2 stopped before tests at script-approval and compilation
boundaries. The actual 49 target-module log digests prove only post-communicate
host logging; 65 original summaries retain nested setup and target statuses.
They do not establish 69 device journeys. All 14 full feature journeys returned
ERROR; only the Scripts mandatory capability gate passed. No complete feature
area, Pico, iOS or other client receives acceptance from this campaign.

The 37 preparation ERROR rows retain genuine missing prerequisites. No native
domain READY existed after an assignment client's `std::bad_alloc`; its cause
remains unknown. Geometry, HTTPS/account, independent peer and native-worker
requirements were not fabricated, and mandatory gates remain strict.

Both exact task-owned HTTP groups and the task's native backend container were
retired within their recorded scope. The old bootstrap Tablet owner remains
unresolved at original-session HTTP 404. A separately identified SDK ADB daemon
outside the frozen mapped namespace was retained without signals because it had
two live connections and exclusive use was unknown. Three same-UID process
environments were unreadable. No global host, transport or device cleanup is
claimed.

See the [current 14-area matrix](INTEGRATED_COVERAGE.md),
[all 69 actual results and evidence SHA-256 values](integrated-campaign-results.v1.json),
[all 37 preparation gaps](integrated-preparation-errors.v1.json), and
[the complete failure/cleanup handoff](INTEGRATED_FAILURES.md).

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

## Planned campaign boundary

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
the earlier partial host component checks. Test results and exact source/build
identities will be appended only after actual execution.

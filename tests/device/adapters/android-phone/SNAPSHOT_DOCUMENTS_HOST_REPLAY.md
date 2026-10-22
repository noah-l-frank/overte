# Snapshot Documents host replay

This packet implements the Android Phone SDK 26–28 Documents producer and its
original-file proof. Full common Snapshot closure is still pending. This is not
Android device acceptance or a complete Android build claim.

| Layer | Qualification |
| --- | --- |
| Public normal input | The existing Phone adapter and unchanged common scenario drive the normal Snapshot UI and Documents drawer, owned root, Save and Back paths. |
| Actual Java and files | A separate JVM runs the unchanged `SnapshotDocumentsEvidence` class. Real files, descriptors, bytes, SHA-256, device/inode identity, write-close callbacks, delete and fresh absence checks execute on the host. |
| Explicit host seams | Android PackageManager resolution, Binder/Phone/provider UIDs, APK identity, kernel/SDK state and native/renderer producers are synthetic boundaries. They do not establish real Android OS behavior. |
| Source and retirement | Native export URI/ID ownership, original byte acquisition, private readbacks and actual provider retirement use the existing strict readers. ACKs never supply measured effects. |
| Full platform | Android DocumentsProvider/chooser integration and hardware execution remain unverified here. No device, ADB, Appium server, installation or Jenkins execution was used. |

The producer is
[`snapshot_documents_journey_boundary.py`](../../../../android/phone/tests/device/snapshot_documents_journey_boundary.py).
It reuses the shared guarded Snapshot target and public harness, including the
separate actor process and credential, actual loopback TLS service and original
v18 close/finalization protocol. Upfront subprocess and transport guards deny
unprovisioned device paths in both primary and actor processes.

The actual Java source is
[`SnapshotDocumentsEvidence.java`](../../fixture/android-snapshot-receiver/java/org/overte/snapshot/SnapshotDocumentsEvidence.java).
The helper compiles that source and the existing host serializer with
`javac --release 8` in this worktree's own `build/snapshot-documents-journey`.
The original Java observation epochs and actual filesystem identities are never
replaced by caller expectations. Only the explicit Android namespace/UID/APK
metadata comes from the host seam.

The independently qualified completed native capture is the only writer input.
Picker launch creates no output file. Ignored Save, an open/failed writer,
foreign URI/UID/APK/window, missing original bytes, a same-bytes foreign inode,
late output and a lost delete reply remain strict counterexamples. Retirement
never adopts or removes an observed foreign replacement.

The Documents reader's opaque acquisition lease removes only a duplicate
pre-binary provider observation. It is reader-owned and single-use, is unavailable
from historical floors, and rechecks current target/installed identity,
monotonic time, actual epoch and original hash before the binary read. A fresh
post-binary provider observation and the final role observation remain required.

The expected-catalog scope processes static reviewed expectations only. Every
lookup still opens, hashes and checks the actual file identity and bytes; every
native group retains its full source/freshness/chronology validation. A final
check also guards complete archive publication. A closed scope cannot authorize
a later read. No observed native/source facts are cached or retimed.

Focused tests are in
[`test_snapshot_documents_journey_boundary.py`](../../../../android/phone/tests/device/test_snapshot_documents_journey_boundary.py),
[`test_snapshot_documents_acquisition_lease.py`](../../../../android/phone/tests/device/test_snapshot_documents_acquisition_lease.py)
and [`test_snapshot_catalog_pass.py`](../../../../android/phone/tests/device/test_snapshot_catalog_pass.py).
The complete SDK26 common test preserves all 15 applicable steps from the
unchanged 18-step catalog; the three Photos-only permission steps are the
catalog's explicit non-applicable cases. Save picker and both Share handoffs
remain included, producing exactly four native handoff lifetimes.

At this packet's handoff, 103 selected source/host tests passed. Four bounded
actual first-Share cycles also returned original primary sources and three new
actor receipts aged 1156/1196/1250 ms, below the unchanged 1500 ms limit. This
bounded diagnostic does not qualify the full common journey. Earlier complete
runs failed the unchanged strict freshness limit:

| Complete SDK26 host replay | Result |
| --- | --- |
| 68.963 seconds | First Share witness exceeded the original freshness bound. |
| 74.591 seconds | First Share witness age reached 1689 ms. |
| 71.077 seconds | First Share witness age reached 1624 ms. |
| 73.513 seconds | Two valid first-Share witnesses preceded a 1616 ms witness. |

The guarded two-stage actor is implemented: it prepares immutable history,
releases the owner lock, then rechecks the original actor/feature/role headers
and target binding before acquiring its own fresh quiet-batch originals. Every
sample retains complete original-file validation and current restoration proof.
The subsequent retained-reader/warm-CAS implementation is undergoing bounded
qualification; its integration is not claimed here. Complete SDK26 replay remains
pending that qualification and a new unchanged common run. Normal operation
deadlines, original clocks and the three-second quiet contract are unchanged.

The current [source coverage review](SOURCE_STATUS.md) distinguishes source and
component checks from complete common qualification. The
[Snapshot guide](SNAPSHOT_FEATURE.md#bounds-failure-recovery-and-complete-retirement)
describes the shared ownership, quiet and v18 closed-fixture retirement contract.

No feature flag, shared capability count, admission source pin or cross-platform
status was updated by this handoff. Pico and iOS remain separate sessions.

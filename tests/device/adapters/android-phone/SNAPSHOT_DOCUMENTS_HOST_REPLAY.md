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
The subsequent retained-reader/warm-CAS implementation is integrated with
targeted ownership and recovery counters. It rechecks actual trusted headers,
reopens all historical originals and reads fresh complete samples; retained
reader continuity never authorizes header adoption or old current facts.
Complete SDK26 replay still needs a new successful unchanged common run. Normal
operation deadlines, original clocks and the three-second quiet contract are
unchanged.

Later complete runs with the storage-intent, distinct-history and ephemeral
Role-lifetime packets still failed the original strict freshness limit: one
stopped at Upload with a 1527 ms peer age after 92.419 seconds; the next qualified
Upload but stopped at background/resume with a 1522 ms peer age after 104.793
seconds. These failed results remain failures. The earlier isolated 203.682 ms
distinct-call charge was not reproduced as a persistent history-size regression
and is not attributed to GC without original causal measurements.

The new `SnapshotConstructorHistoryPass` moves complete immutable Primary
constructor file replay between two source-lock stages. Admission is limited
to known nonempty ready Primary history in baseline/active state without a
pending action or OS handoff. Original owner headers, manifest prefix, exact
SDK scope/configuration/binding and fixture phase are pinned while locked.
Unlocked replay retains every actual file/hash/schema/image/metadata check and
its five-second bound, but grants no native, input, recovery or publication
authority. The ordinary constructor runs all source factories and continuity
floors after reacquisition; exact first-header validation, full native/phase
requalification, sealed file receipts and historical graph checks precede any
normal current read. Actor, pending, OS and cleaned paths retain their existing
guards. Lost known journals or remaining unframed PNG/binary/observer ownership
cannot silently become a new baseline.

Fourteen direct
[`constructor-pass counters`](../../../../android/phone/tests/device/test_snapshots_constructor_history_pass.py)
passed together in 52.707 seconds. They exercise actual files and metadata,
owner/scope/phase/graph failures and a real separate lock-owning process during
an original-file read. Eight
[`ephemeral-reader lifetime cases`](../../../../android/phone/tests/device/test_snapshots_ephemeral_role_disposal.py)
also passed in 50.175 seconds. The latter release only the operation-owned
reader's own references after all guards and finalizers; stored files, returned
DTOs, durable journals and retained Actor readers are unchanged. Production GC
policy is unchanged. These targeted host results do not establish the new
pass's full-journey timing or qualify SDK26/SDK29. Both complete host backend
qualifications, the final integrated-source audit, the Android APK build and
physical device acceptance remain separate and unverified here.

The first complete constructor-pass replay also remains red: the unchanged
SDK26 method failed at `12-share-cancel` after 58.683 seconds. Two unseen
same-ticket Actor rows were already in the journal: sequence 33 was 2145 ms
old and sequence 34 was 1075 ms old at the recorded reader boundary. Both had
been fresh at actual publication receipt (206/202 ms). The common engine
correctly rejected the older unseen row; the newer row cannot erase it.
During that Primary observation, a second Actor acquisition overtook the
unlocked historical replay. The measured second lock wait was 806.136 ms,
followed by an 836.316 ms Primary lock hold. This is a scheduling failure;
no individual hash or GC cause is inferred. Ordinary Actor scheduling has since
been revised as described below. This failed result remains red; the revision
must qualify a new unchanged full run while preserving every journal row,
independent actual reads, strict freshness and unchanged cleanup quiet checks.
The preceding targeted join passed 91 tests; neither that result nor this
failed replay qualifies the full backend.

The Actor journal is version 3, with exact typed migration from original
process-bound versions 1 and 2. It retains `primaryCue`, null or a version-1 cue
holding the actual Primary ready-role header. The gate validates the original
manifest prefix and latest completed Primary frame's active phase/ticket before
admitting a new ordinary measurement. An unchanged frontier waits. A greater
ready sequence is only a scheduling cue: the Actor still reads its own current
native/VM/files/provider originals, supplies its own time and Role sequence and
uses its independent publication credential. No Primary expected state, source
fact or receipt is copied. Actual cue and independently acquired pending sample
share one own CAS, with Primary-owner checks after the native guard and after
the write. Cold pending/receipt recovery retains that pin and precedes the gate.
Cleanup quiet and closed-fixture proof remain ungated by Primary advancement.

The six new
[`actual scheduling counters`](../../../../android/phone/tests/device/test_snapshots_actor_primary_cue.py)
and fifteen existing Actor tests passed in 47.168 seconds on Actor source
`c0924e8d93c8ba2e010a7bbcb589fbd026d8cee81b3e57be74973aa759f8dfea`.
The separately reported eight phase/migration checks passed in 43.836 seconds
on the earlier `5dce` source; they are historical targeted evidence, not a run
of the subsequent cleanup-only adjustment. That adjustment retains the same
ordinary scheduling methods. Its close deferral requires already durable own
quiet completion and a matching actual cleanup receipt, keeps any partial Role
read's exact owner for fresh closed reconstruction, and supplies no success or
retirement itself. The new dedicated close-race test result remains pending in
this handoff. No complete SDK26/SDK29 host result, final integrated-source audit,
complete Android APK build or physical-device acceptance follows from these
component checks. The source-qualified count remains thirteen of fourteen.

The current [source coverage review](SOURCE_STATUS.md) distinguishes source and
component checks from complete common qualification. The
[Snapshot guide](SNAPSHOT_FEATURE.md#bounds-failure-recovery-and-complete-retirement)
describes the shared ownership, quiet and v18 closed-fixture retirement contract.

No feature flag, shared capability count, admission source pin or cross-platform
status was updated by this handoff. Pico and iOS remain separate sessions.

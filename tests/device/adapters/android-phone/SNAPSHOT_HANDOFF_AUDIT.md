# Passive Snapshot handoff audit, 2026-10-22

Scope: parent `715b39e391`, integrated source packet `4c1b95825f`. This audit
changes only the Phone E2E sampler, its Account read gateway, SDK source reader
and focused tests. Product behavior, Documents sources, Appium, probe, pins and
runner remain outside this packet.

## Confirmed findings and repairs

1. **Expired first retirement could erase a missed deadline.** `retire()` set
   retired before sampling; the sampler's active-only monotonic expiry check
   then skipped a lease that expired while Qt events were paused. A first
   retirement now checks the actual original monotonic lease before changing
   state. Expiry remains a sticky incomplete source even after timer shutdown.
   A sample that itself crosses the active deadline also stops incomplete.

2. **Outer sequence progress did not preserve nested VM originals.** Six
   regression counterexamples initially passed malformed provenance: erased
   require, compilation, ScriptCache load and entity-effect history, changed
   original resource-root representation, and a previously removed manager
   returning after an intermediate frame. The SDK now delegates pure history
   transitions to the existing NativeScriptObservation owner and retains its
   full bounded retired-manager/engine state across acquisitions. Roots advance
   from the preceding group's final original root, with exact source identity.
   Context requests cannot precede the previous original context capture.

3. **Account owner-thread waiting could block forever.** The existing context
   read correctly dispatched to AccountManager's QObject thread but used an
   unbounded BlockingQueuedConnection. A stopped/stalled owner queue could
   hold the sampler/GUI indefinitely. The E2E helper now uses the same original
   owner and a bounded 1000-ms queued read. All queued result ownership is on
   the heap; no caller-stack references survive timeout. A cancelled late
   callback skips its getter, and a relocated/deleted/stopped owner cannot
   supply a current result. Failure keeps the native source incomplete and
   prevents successful retirement evidence. Other original getters retain
   their existing implementation and pending/error behavior.

4. **Cached control samples could forget prior retired jobs.** Control observe
   could accept an unchanged native sample while its separate job inventory
   lost an earlier original job. Cached samples now require that inventory
   unchanged. New acquisitions use the full append/retirement transition.

The passive SDK reader additionally exposes `restore_history(frames)` for at
most 512 immutable original envelopes. It replays the original validation and
all nested histories without transport access. Restored evidence never counts
as a fresh acquisition; the next read must advance actual native sequence.
Its caller must retain the original envelopes and binding in its existing
durable owner. The control reader rejects host-clock rollback before issuing
another request. No desired result or source field is introduced.

## Evidence and limits

`test_snapshot_handoff_audit.py` contains six host tests with the rollback,
resurrection, reconstruction, cached-job and clock counterexamples. The ten
existing SDK handoff and seven measurement tests also pass.

`test_snapshot_handoff_audit_native.py` compiles the actual native sampler,
actual FeatureLifecycle and the extracted actual Test gateway with explicit
Account/getter seams. Seven native host tests cover the original GUI lifecycle
thread; direct/queued owner relocation; stopped and stalled queues; cancelled
late callbacks; actual gateway Account dispatch; and sticky source failure on
gateway retirement. Its expiry test sleeps the real **60030 ms without Qt
event processing**, then performs first retirement. No clock injection,
shortened TTL or weakened freshness is used. The complete seven-case file took **70.340 seconds**, including both actual
Qt compilations and the real lease. It stays separately budgeted from the
existing 60-second native expiry file; a 90-second per-file budget is sufficient
for the observed host run.

The existing native gateway's normal acquisition/strict retirement, missing
getter and default-off cases also pass against the changed helper. Original
AccountManager provenance was reviewed in its own guarded getter; the complete
AccountManager/TestScriptingInterface product translation units and Android
runtime are not compiled/executed by these extracted Qt checks. No installation,
device, network, Jenkins or physical acceptance result is claimed.

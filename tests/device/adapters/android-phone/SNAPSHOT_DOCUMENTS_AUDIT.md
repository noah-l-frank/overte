# Snapshot Documents SDK audit

Audit basis: `5a54eed7e0`, including the controlled provider and the ordinary
DocumentsUI/independent original-byte SDK reader. All inputs in the host tests
are explicitly synthetic Android/SDK boundaries; no device picker was used.

The audit reproduced three failures before correction:

* A drawer/sidebar label with `android:id/title` counted as the selected fixture
  directory. Selection returned without a touch; a foreign toolbar title plus
  that label subsequently admitted Save. Independent provider bytes would
  still reject feature success, but the input already exceeded fixture scope.
* A reconstructed read-only reader retained process/root metadata without the
  original document/FD history. It accepted empty retired arrays that the live
  reader correctly rejected.
* A final epoch read could lose ownership, exceed the five-second deadline or
  regress the monotonic clock after the last checks, yet return a complete
  provider observation or retirement.

Current-directory admission now requires one enabled, visible original toolbar
title. An Android framework title additionally requires an original toolbar
ancestor. Visible root-drawer containers, ambiguous toolbar titles and plain
drawer/list labels do not authorize Save. Unsupported OEM layouts remain red.

The closed binding is version 2, with exactly:

```
snapshotDocumentsBindingVersion: 2
installed: {package, apkSha256, uid, processId, processIdentity}
instance, runId, armId
root: {rootId, path, device, inode}
floor: <complete original Snapshot Documents source DTO, version 1>
```

`floor` retains the original nonce, sequence, timestamps, plans, documents and
FDs verbatim. It is an ownership lower bound, not an independent actor read.
Even the first current observation must advance it and preserve its history.
Old metadata-only bindings are rejected. `binding()` exports the latest actual
source as its floor; a durable owner should retain its original binding once.

`restore_history(original_rows)` accepts 1–512 original provider DTOs on a virgin
bound reader, validates each at its original captured epoch, requires the exact
bound floor in the sequence, and replays full continuity atomically. It sends no
transport request and does not retime samples. An actor can restore
`[binding.floor, *ownIndependentOriginalRows]`; the next read must obtain a fresh
nonce and strictly advancing native sequence at the actual current epoch.

Final provider and retirement epoch reads are followed by ownership and
monotonic deadline checks. Binary acquisition likewise uses one final measured
monotonic value. These checks do not qualify acknowledgements as effects.

Validation: 17 independent provider-reader tests and 10 DocumentsUI tests pass,
including the new history, floor, real-toolbar, foreign-directory and final
clock counterexamples. The pre-change provider/native/OS/UI group also passed
32 tests in 6.115 seconds; its synthetic Android seams executed the actual Java
provider and native SAF owner. No source in the Java owner changed in this SDK
packet. Full Android/Overte compilation and real SDK 26–28 UI behavior remain
unverified here. No devices, installations, network or Jenkins were used.

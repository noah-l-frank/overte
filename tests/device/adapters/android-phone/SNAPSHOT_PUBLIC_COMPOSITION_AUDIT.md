# Snapshot public composition audit

This independent host audit covers FastCancel `a1ebf9305c` and the ordinary
Save/Share handoff input `8091698d33`, including the corrective packets
`2ec046757a` and `4136000a68`. It does not declare the still-unregistered public
Snapshot facade or its full common journey complete.

## Findings and corrections

Four independent OS-input counterexamples reproduced against the original
handoff-input packet. A durable admission could consume the original 60-second
native lease or the original widget plan's freshness window before the sole
write. The actual Appium factory also failed to rehash the installed candidate
between admission and that write. Packet `2ec046757a` adds the missing checks in
the helper and the actual factory, retaining the original plan and unchanged wire
command. The fourth counterexample crossed the lease deadline in the final OS
guard after reading an otherwise valid original receipt; `4136000a68` brackets
that guard with the final native clock and monotonic deadline checks. All four
independent counterexamples pass against the corrected sources.

FastCancel's previously reported complete-current history floor is independently
checked against an actual Qt-produced closed DTO. A legitimate later native
history append remains acceptable. A subsequent individually valid DTO that
still preserves the retired recipe prefix but drops that later acquired history
is rejected. Replacement of either original native or Script history instance in
retirement or current is also rejected.

## Composition and limits

The input audit composes the original SnapshotSystemContext and
SnapshotDocumentContext with the one-send helper. Explicit synthetic native,
SDK, clock and private IO producers model the transition from foreground
AppState 4 to the originally resolved chooser or DocumentsUI in AppState 3.
Foreign windows, another activity in the same package, a mismatched Save/Share
OS scope, lost authority, or changed source/artifact/PID/session/generation/target
remain red. A denied prewrite scope sends nothing, but its durable issued intent
cannot be replayed. An expired original lease cannot even admit a new input.

A lost write response is recovered after the original widget plan becomes too
old for a new input. Recovery returns the unchanged original receipt, without
retiming the archived plan, new foreground admission, a new write, or a new
durable admission. The actual Appium read-only factory is exercised separately
and does not construct a foreground runtime. Missing or changed original receipt
and expired lease remain red. A valid receipt plus an unchanged independent
native callback stream fails both Save and Share effect reducers.

These private APIs still require the facade's durable authority to bind the
exact archived plan, handoff lease, application context and issued intent.
The facade must archive every independent original, recover only those exact
owners, and finalize the original journals and native workers after Review is
closed and the fixture phase ends. No receipt is proof of OS consumption or
file creation. This audit does not substitute for that pending public facade,
separately credentialed observer, complete common journey or closed-phase
finalizer test.

## Validation

All checks ran only in the independent audit worktree:

- `test_snapshot_handoff_admission_audit.py`: 11 tests, 0.120 s, pass.
- `test_snapshot_cancel_followfloor_audit.py`: 2 tests, 15.697 s, pass. Actual
  Qt6 component compilation, extracted original Test gateway, original Snapshot
  QML, actual Qt mouse/timer execution and actual closed DTO; subsequent
  acquisitions and appended capture rows are explicit synthetic producers.
- Existing `test_snapshot_handoff_input.py`: 11 tests, 0.028 s, pass.
- Existing `test_snapshot_system_context.py`: 5 tests, 0.005 s, pass.
- Existing `test_snapshot_documents_ui.py`: 10 tests, 0.014 s, pass.
- Existing `test_snapshots_measurements.py`: 13 tests, 1.361 s, pass.

The Qt component test builds in a unique temporary child of the audit
worktree's build directory. It does not compile the complete product or Android
application, exercise an Android OS, or establish visual acceptance. Native
expiry implementation is unchanged; the prior real 60-second expiry audit was
not redundantly rerun. No devices, installs, services, network or broad runtime
runner were used. Runner registration and shared source pins remain central
integration work.

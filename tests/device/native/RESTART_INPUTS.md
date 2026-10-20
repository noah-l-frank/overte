# Normal restart inputs and native lifecycle, version 1

`adapters/restart_inputs.py` supplies private one-send input intent for a normal
app stop/launch pair. It composes with the existing Script ownership handoff;
it is not a full journey, process-death verdict or complete feature capability.
The three platform factories still need to connect these methods to their
ordinary `app.stop`, `app.process` and `app.launch` operations and original native
feature source. No platform binding or real device input is enabled by this
shared component alone.

Construct `RestartInputs(store, owners, component_only=False)` with the existing
private input store and exactly three distinct private ownership stores in the
same parent: handoff, original Script files, normal Script manager, in that order.
Their exact absolute host paths are frozen in the private journal. They must
never appear in a public operation result. Reconstruction cannot substitute
different empty paths to conceal unresolved ownership. Ordinary context schemas
and explicit iOS component-only scope are unchanged.

`capture(binding, native_feature_reader, handoff=prepared_handoff)` reads the actual existing
`NativeFeatureObservation` source, checks the original positive PID/native birth,
persisted lifecycle counters and matching process context, then records input
intent. The joined Script controller first prepares the actual handoff. The
optional typed handoff parameter requires its original PID/birth/binding to
match this capture and pins the exact ownership-store paths. Its validated
original prepared snapshot is saved privately for completion-receipt recovery.
Do not derive this baseline from requested operations, host launch count, an
input ACK, or a cached controller record.

`stop(deliver)` accepts only phase `prepared`. Persist `stop-issued` before
calling the ordinary guarded stop function exactly once. Return its original
receipt unchanged. An exception, timeout, invalid receipt or late final clock
never resets the issued phase. Calling Stop again is refused. If the controller
dies after journaling but before delivery, this conservative intent still must
not cause an automatic replay.

`launch(stopped, deliver)` accepts only phase `stop-issued`. Require a separate
current OS application-state read with exactly `running:false,identity:null`
before writing `launch-issued` and delivering the ordinary guarded launch once.
Missing, malformed, failed or running OS observations must raise, not become
empty state. The platform callback must revalidate the original candidate/target
and existing native session; it must not install, reset or silently recreate an
unqualified session. Each stop/launch method has a thirty-second monotonic bound
including preflight, private writes and original delivery. Product/platform
operation limits remain in force. A successful Stop ACK alone cannot launch the
next stage.

The OS application-state precondition is narrower than old-PID death. The
separate [handoff](SCRIPT_RESTART_HANDOFF.md) must still require original native
`ESRCH`, a genuinely new native PID/birth and current empty execution/UI plus
unchanged original files. Unavailable OS/kernel sources cannot be substituted
with default absence. Neither input method reports any functional success.

`observe(binding, native_feature_reader)` is read-only with respect to the
product. Require an unchanged selected source/artifact/target, nonregressing
generation, changed actual PID and native birth. Require original native
`launches == old.launches + 1`, `activations >= old.activations + 1` and
`backgrounds >= old.backgrounds`. These are assertions against raw measured
values, never returned synthesized counters. `FeatureLifecycle.h` already
persists these counters in the same isolated `feature-lifecycle.v1.json`; no
requested-operation summation is necessary. A different results directory,
ignored launch, missing activation, extra restart or producer reset fails.
Return the original complete native packet unchanged. Subsequent observations
pin the same new binding/PID/birth and cannot regress previously recorded counts.

The exact private envelope has `restartInputVersion:1`, `componentOnly`,
`ownerFiles`, `scriptHandoff`, `oldBinding`, `oldNative`, `phase`, `newBinding`, `newNative`.
Native summaries are exactly `pid`, `instance`, `lifecycle`. Phases are
`prepared`, `stop-issued`, `launch-issued`, `observed`. The two new fields are
null until actual new-process observation; input receipts are never stored as
lifecycle evidence. `scriptHandoff` is null for standalone input ownership; the
joined Script controller requires the original validated prepared snapshot.
It contains private file ownership and must never become a public artifact.
The existing private-file type, permissions, atomic replace,
fsync and compare-with-previous checks apply. No raw SDK exception is journaled.

Recovery inspects the issued phase and reads actual OS/native state. It must
never call an already issued input again. If the native source remains
unavailable or the original app never stopped, leave intent unresolved. Keep
this input journal throughout the remaining Script workflow. Only after full
independent engine/effect/UI/file cleanup and retirement of all three pinned
owners may `retire(binding, native_feature_reader)` reobserve the same native
process/lifecycle and discard input intent. It does not delete the other owners
or establish their native cleanup itself. The full adapter's general cleanup
must also refuse a remaining restart-input journal.

`run_script_restart` composes these same primitives and original platform
callbacks. It never repeats an issued input on reconstruction. Only SDK delivery
exceptions become privacy-safe `RestartDeliveryUncertain` failures. The current
call stops immediately; reconstruction may resume through independent current
OS/native proof without replaying the issued input. Deadline, malformed state
and preflight failures also remain failures; no input exception is swallowed.
After actual new native lifecycle observation, invoke the existing handoff's
full independent exit/absence/file/UI verification. Return its original raw
proof and original lifecycle packet, not a synthesized feature observation.

If the caller lost the handoff return after both binding writes and journal
retirement, use the saved validated prepared snapshot to reconstruct only
the host transaction with the already transferred exact new records. A changed
owner, manager cursor/state, binding, PID or birth cannot be adopted. Repeat
the whole native proof/quiet window before returning. Product files are not
recreated and normal app/Script/UI inputs are not replayed. A remaining input
journal continues to block general cleanup until the complete feature cleanup
has independently retired the three pinned resource owners.

Fourteen input cases and nine joined-controller cases use actual private journals and synthetic OS/native
boundaries. They exercise original counter readback, lost ACKs, ignored Stop,
old/native foreign/missing/stale sources, duplicate delivery refusal, changed
candidate/target, extra starts, missing activation, third process, counter
regression, wrong/remaining owners, explicit component-only scope, clock/deadline
failures and malformed private state. Joined cases additionally exercise real
temporary original fixture bytes, the actual handoff transaction, lost SDK or
handoff receipts, retained intent/partial recovery and no restaging/input replay.
No native code, app or device is executed.

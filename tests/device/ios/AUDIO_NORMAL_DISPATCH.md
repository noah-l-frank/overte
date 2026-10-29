# Normal Audio runtime action dispatch

[The existing runtime](adapters/audio_runtime.py) now delegates typed ordinary
Audio actions to its held [recorded owner](adapters/audio_recorded_owner.py).
The owner's existing 25-second operation budget covers the complete call.
It checks the current shared action grammar, selected PCM profile, original
run, fixture, owner path, saved scope and fresh phase/ticket before routing.
Phase metadata authorizes inputs; it does not prove their effects.

Record-start uses the existing authorized-start owner. Background-resume uses
the existing background owner. Other verbs use the recorded owner's existing
actions. Await-completion captures and retires the existing PCM lease; Close
uses the already configured original Close callback. No new journal or input
replay mechanism is introduced.

An uncertain Home return must reach the background owner's original recovery
before asking the parent to prove foreground again. Parent lock, unchanged
WAL, saved scope and current input phase remain checked before that handoff.
The background owner's original SDK/process/session guards remain mandatory,
and the parent's full live guard runs after recovery. Ordinary foreground
actions keep their initial live guard.

The same live recorded owner now has an explicit internal entry route under
that operation budget. Every invocation reopens its actual scope, current
binding, parent and typed child histories. Fresh read membership must cover all
Audio files in both state and artifact roots, and original inventory leases
check their bytes and identities. Unknown Settings responsibilities and orphan
children remain unresolved. Ordinary InstalledAdapter entrypoints retain their
ownership barrier, including while this internal route succeeds.

## Host verification

Six boundary/recovery checks, one new normal fourteen-action runtime flow and
the existing required PCM/Close fourteen-action regression passed. The normal
flows retain all five authorized starts, cycle-3 PCM retirement and cycle-5
Close evidence. Lost start and Home returns preserve exactly one original
delivery, including one Home/Activate pair. Foreign scopes, stale tickets and
unknown profiles refuse input.

The three selections retained 305 original files in eight genuine temporary
roots, with all 7,772 source/launcher pins unchanged. Actual fixture cleanup,
thread and process checks completed; no Node process was selected by these
cases. Local reports are retained in
`.ios-host-tmp/audio-next-normal-runtime14-dispatch-root3-preparation-20261029`.
Existing default helper mode retains its original manual dispatch path.

The subsequent held-owner change passed seven new ownership counterexamples,
six existing boundary/recovery checks, seven ordinary entry-barrier checks and
the complete normal fourteen-action runtime flow. Those 21 tests retained 222
original files in 21 genuine temporary roots; all 7,779 source/launcher pins,
cleanup checks and post-stop censuses remained stable. The runtime flow took
124.746 seconds in unittest. These receipts are retained in
`.ios-host-tmp/audio-next-held-recorded-entry-root4-preparation-20261029`.

This is an internal component connection. Public InstalledAdapter/configuration
admission, independent acoustic/peer evidence, permission restart and typed
process/SDK end remain open. PCM source models do not qualify a microphone or
physical ADC. No native build, SDK execution or device test was performed.
Complete areas remain 5/14.

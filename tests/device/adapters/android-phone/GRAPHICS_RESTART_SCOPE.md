# Original Phone Graphics process transfer v2

Scene and preference journals are now version 2. They retain a complete original
old-process archive and admit one explicitly proved new process without relabeling
old packets as new observations. Version 1 pending journals are refused; no silent
migration/reconstruction can invent missing process or original-source proof.
The closed receipt validator and durable record builders are now composed by the
[normal restart coordinator](GRAPHICS_RESTART.md). The complete independent
Graphics coordinator remains required. No full
capability is advertised. Native instrumentation is uncompiled and devices untested.

## Closed restart receipt v1

`overte_phone_graphics_restart_proof.validate` accepts exactly
`{input,oldNative,native,exit}`. `input` is the existing original `RestartInputs`
v1 record in `observed` phase, with no Script handoff. It preserves original
old/new bindings and native PID/source/lifecycle projections. Candidate revision,
artifact SHA, exact session, generation and target fingerprint must agree.
Both bindings require actual Phone PID/start-tick identities. Original old/new
PIDs and native births must differ. New original launch/activation counters must
satisfy the existing restart contract. Full original native packets must match
both projections exactly and retain canonical request nonces/original request
clocks; the new request cannot precede the old original sample.

All actual original Graphics fields in the first new native sample must equal
the last old sample, before any settings input. This is persistence proof, not a
request to set preferred values. `exit` must be a canonical original native kernel
query from that same new process/source for exactly the old PID, after the new
native sample, with actual `ESRCH`/absence. Permission/unknown, Stop ACK, changed
PID alone, different query/source, changed candidate, missing clocks or replaced
preferences are insufficient.

## Scene journal v2

The original v1 scene fields remain, plus nullable `handoff`. A non-null handoff
has exactly `previous` (complete immutable v2 pre-restart journal), `receipt`,
`subject` and `loads` (first independent actual new-process packets). Its previous
archive must have no handoff, active phase, complete original preparation and
empty UI leases. The receipt's exact owner-file list is the actual scene journal
and the two role-specific world-render journals. The restart controller must
independently drain those world owners before Stop.

The original user-scene/feet/view/load packets remain byte-for-byte in their old
process context. New subject packets must have the new native source birth, all
seven run UUIDs initially absent, and original request time after the first new
native sample. New complete scene-load history must have a different source
birth and begin no earlier than the initial new subject. Fresh current cursors
must advance only within the new process; old source prefixes remain immutable
archives. Cross-process clock/cursor reset is never treated as continuation of
one native source.

`PhoneGraphicsScene.restart_record` builds a proposed CAS value without applying
it or returning measurements. Normal construction and pure `archive()` validate
the entire nested original chain. A second transfer/nested restart is refused.
The complete controller must durably save proposals before either scene or
preference CAS replacement and recover partial application from their exact
original/proposed values.

Fresh `prepare()` then uses new ordinary Go To inputs and independently reacquires
controlled entities and measured camera-to-feet alignment. It preserves the
immutable original scene ticket. Foreign new-process UI is refused before input.
If restart returned to a legacy camera mode, only the normal View > First Person
menu may select `first person look at`; that one-send action has separate durable
ownership and actual new mode proof. Final restoration compares new-process
original samples against the unchanged old user-scene/feet/view/foreign-scan
archive; no historical packet becomes a current measurement.

## Preference journal v2

The original fields remain, plus nullable `handoff:{previous,receipt}`. Its
previous v2 archive must have no earlier handoff or cleanup, and must be ready
or acknowledged. Its last native packet is exactly the restart receipt's old
packet. The new scene must independently carry that identical receipt. Frozen
original preferences remain in their actual old PID/source context; the new
current native packet begins at the original new-process receipt. Original
resolution/Haze/Mirrors are never refrozen from the changed post-restart state.

All old tickets remain retired history. The old current action is cleared; a
reused old ticket cannot be sent as a new action. New action/native/UI histories
advance only from the new process. Normal `restore-original` and cleanup use the
unchanged original values for input and independently measure current new native
effects. The existing complete original-Graphics/closed-UI cleanup proof remains
mandatory. `restart_record` only builds an unapplied proposed CAS value;
`archive()` supplies pure historical validation without SDK/source admission.

Ten host cases use independent synthetic old/new native, scene-load and kernel
sources with real private CAS journals. They cover preserved non-default originals,
full new-process restoration, refused old-object input, unknown/wrong-PID kernel
evidence, candidate/preferences/lifecycle/birth mismatches, absent/foreign archives,
pending old ownership, differing scene/preference receipts, refused v1 records,
normal camera recovery, forbidden old-packet relabeling and SDK-free archive
validation. Their receipts are explicitly simulated; no application process was
stopped/launched and no physical restart was qualified. Full normal restart input,
per-role sample archives, partial-CAS recovery and feature orchestration remain
required before enabling Graphics.

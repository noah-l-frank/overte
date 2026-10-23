# Actual remote Chat cleanup prefix

`ChatRemoteCleanupPrefix` version 1 joins the original shared cleanup callback
to a warm original primary cursor and an originally live independent Actor's
qualified publications. It writes one Stop2 request. Its `completed` flag means
that prefix/request transaction returned successfully; it does not mean that
the Actor stopped, the application restarted, resources were archived or the
whole feature completed. Public Chat capability remains disabled.

The caller attaches `ChatRemoteCleanupSlot.callback` to the actual `Journey`
before execution, then binds the consumer when the original cleanup cursor is
available. The slot accepts exactly one invocation with the same original
`Journey.cleanup_consumption` bytes object while its real cleanup hook is
running. It cannot qualify a caller-supplied result or run a second baseline.
The actual shared checker must already have consumed its stable three-second
cleanup window. `sequenceSucceeded` is retained exactly from that checker;
direct `wait/consumed_cleanup` fixtures remain false and cannot qualify full
shared execution.

The primary cursor must own the original cleanup stage, with no cleanup reads
yet. Its run, fixture, bindings and exact lock objects must match the independent
reader. The Actor start comes from the actual Journey's previously consumed
witness, matched to original independently received rows. Primary and Actor
sequences remain distinct. No caller offset, phase count or unconsumed Actor
tail replaces either original cursor. The Pico factory additionally binds the
actual Parent cache-release owner, fixed primary/witness paths and an unchanged
Parent admission guard. Its result root and rootless chunks block ordinary
cleanup. Full construction through this Pico factory is still unqualified;
premature/unknown construction and retention are checked separately.

During the actual common wait, `observe()` returns a fresh original primary
query and `received()` returns the independently qualified journal. The callback
then matches every consumed primary sample to its actual global/source row and
every consumed witness to the literal independently received row. Genuine
earlier attempts with no witness remain attempts with no Actor proof; they
cannot replace the actual stable three-second window or its last witness.
The current version expects the enclosing original runner to handle actual
Actor readiness: an expected `PhasePending` is not fabricated into a peer
observation, and the shared checker is not changed to accept it.

The consumer preserves the unchanged cleanup bytes' SHA-256, original header
and all consumed sample/reference rows in new immutable private chunks. Only
after these originals exist does it write `stop-issued` with a fresh command
ID, exact original Actor instance/run/ticket, actual last consumed sequence,
payload digest and actual cleanup-consumption digest. It freezes the same warm
reader and rechecks the original primary and independent source clocks after
that final intent CAS. Only then does the original empty Stop store receive
one write. The physical Stop bytes/stamp are retained in `stop-requested`.

Final copies, guard/CAS work and actual outer lock exit stay inside the same
original 1.5-second clocks. Fresh HTTP phase metadata never refreshes old native
facts. A late intent CAS performs zero Stop writes. A lost Stop-write reply
retains the exact original intent and never resends, even if a completed-looking
Stop file exists. Failed consumers quarantine both original source objects;
uncertain journals are not retired, reconstructed or replayed.

The Stop2 consumption digest is now derived from the actual shared callback,
rather than accepted as a caller success field. The Actor still independently
checks the requested original publication and preserves every additional
same-ticket tail row in its complete seal. A separate
[typed original return](REMOTE_ACTOR_RETURN.md) must admit that full historical
graph, consume its fresh original nonce and prove actual original process
absence. Original application/profile/restart/IPC, whole archival and final
Parent host closure remain separate required joins before fixture closure or a
whole-feature result. This component does not infer those outcomes from a Stop
request or source receipt.

The host source fixture keeps its actual primary flow/cursor in the Parent.
A separate owned Python worker creates its own original Actor, publisher,
cursor, source journals and two real captured descriptor pairs. It independently
requests the same actual fixture coordinator through test-owned stdin; only
ordinary raw fixture requests/responses cross that channel. No live owner is
serialized or constructed from another process's files. Native producers,
widgets, Parent admission and the remaining 24 input effects remain explicit
seams; no product, AssignmentClient, device, service or HTTP server starts.

The first arrangement correctly failed primary-source admission (1.051 seconds):
the older Actor fixture had itself created the primary transcripts. The test
was changed to preserve their original warm Parent ownership. A fixture opcode
mistake then failed in 0.945 seconds. A later 11.172-second run exposed reuse of
already observed native reader wrappers; each new stage now acquires fresh
wrappers, matching the actual factories. The next run reached the real common
three-second baseline but failed a wrong private cursor `final()` call signature
(43.127 seconds). Only that call was corrected, without changing any bound.

The resulting actual Parent/Actor baseline → Stop2 → preserved extra tail →
fresh nonce → real normal host return/ESRCH case passed 1/1 in 67.363 seconds.
Its header remained `sequenceSucceeded=false`. The actual full typed graph
contained the two additional real same-phase publications after the consumed
prefix. Five focused clock/freeze/Root/factory/retention cases subsequently
passed in 17.078 seconds. Two actual common-baseline counters passed 2/2 in
82.587 seconds: frozen-host/native+2000ms after the final intent CAS produced
zero Stop writes, and a lost real Stop-write reply produced exactly one attempt
with no successful completion or replay. The unchanged positive was not rerun.
The eight existing remote-publication cases also passed against version 2 in
13.028 seconds, without repeating the two new clock/freeze cases. All four
repository checks passed; documentation validation covered 617 Markdown files.

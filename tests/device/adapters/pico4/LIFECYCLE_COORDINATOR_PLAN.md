# Lifecycle v16 private operation composition plan

This is a source-level plan for the existing sixteen-action recipe in
`feature_journeys/scenarios.py`, through the unchanged `OverteSession` and
`Journey` contract. It is not another journey or an executed whole-flow result.
Source3 has actual canonical-factory coverage, fresh readonly observations and
the existing baseline/Back wait consumer. It has no action, independent Actor,
artifact, cleanup or public-capability authority.

The subsequent [private operations continuation](LIFECYCLE_OPERATIONS_BACKGROUND.md)
executes the first seven normal actions through the existing owners, common
waits and optional exact transport fences. The rest of this document describes
the full route; it is not a sixteen-action result.

## One original graph and exact action boundaries

Construct the existing Editor, XJoin/World and Restore/Process graph in one
canonical namespace with the exact same source-lock object. Call original
`Restore.begin()` before any normal Create input. It establishes the actual
process/pose/domain originals; disconnected/serverless is admitted only from
the original native versioned source. Lifecycle does not require a mixer or
domain merely because other feature journeys do. Create Source3 through
`_lifecycle_observation_readonly_begin`, then perform the unchanged initial
wait. Lazy Chat, Background, Pending and Close owners must be attached under
that same continuously held lock at their actual preparation, using Source3's
existing original absence and handoff rules.

The private operation dispatcher must validate the exact next expanded recipe
verb/inputs and original fixture ticket. It records a durable parent intent
before invoking the corresponding existing child methods. Requested or
expected states never become returned observations. Each checkpoint is still
consumed by the unchanged common wait; do not invoke a multi-action helper that
passes a checkpoint before its common consumer has observed it.

| Common action | Existing normal owner methods and boundary |
| --- | --- |
| 1 open Create | `editor.tablet`, `open_create`, `focus_create`; stop focused, before typing |
| 2 type Unicode | `editor.type_create`; original field and UI readbacks |
| 3 first World input | `world.world_input(editor_id=...)`; actual gesture consumption while editor blocks motion; original release/quiet before Back |
| 4 Back | `joined.back_once`; actual X envelope/neutral and original context retirement |
| 5 open Chat | lazy `chat.prepare`, `open_chat`, `focus_chat`; attach actual owner |
| 6 type reply | `chat.type_chat`; never Send |
| 7 background/resume | lazy Background `prepare(chat)`, `run_owned`; once-only existing OS routes, native hidden timer and both full quiet windows |
| 8 open Scripts3 | lazy Pending `prepare`, `back(False)`, `open_scripts(False)`, `mutate('focus')` |
| 9 type retry | `pending.mutate('type')` |
| 10 hold Unicode | `pending.mutate('hold')`; actual original pending event, conservative original birth and strict 10 s deadline |
| 11 replace context | `pending.back(True)`, `open_scripts(True)`; original Scripts4 field, no focus/type |
| 12 deliver stale | `pending.mutate('attempt')`, existing `release`/quiet; original retired-context rejection, no resend |
| 13 close editor | lazy Close `prepare`, `press`/reconcile for its two normal X commands, full original pending/closed/neutral joins |
| 14 second World input | `world.world_input()`; actual original feet/gesture displacement and held direction |
| 15 release | `world.release`; full original release window and unchanged common negative wait |
| 16 restore | `restore.restore(close)`; normal Home/GOTO/field/submit Location-only address, original pose/scene equality, actual Prepare window |

The existing `run_create_world_back` and `run_pending` are component evidence,
not the full dispatcher: they execute multiple common actions before returning.
Reuse their individual methods and recovery phase checks, not their entire
loops as one substituted action. Lost parent/child publication or unresolved
input fails closed and retains original journals. Passive original status may
reconcile an already-issued command; it must not repeat that command.

## Phase and transport fences still to connect

Use an independent `PhaseFixtureReader` for area `lifecycle-input` and the
existing `PhaseInputFence` grammar, with a typed Lifecycle wrapper whose
`original()` returns the currently issued parent row's actual fixture packet.
The parent must retain complete activation-prefix originals, child admission
and final observations. No ACK, caller ticket or expected state is a phase
source. A foreign/retired/changed activation prefix refuses before input.

For every real input within each common action:

1. Freshly mark the exact phase before the durable child intent.
2. Preserve the child's original durable command/envelope CAS and ordinary
   source/candidate/PID/install checks.
3. Recheck the same original phase after the last child CAS, immediately before
   actual Qt/OS/native publication. A fresh HTTP reply cannot erase time spent
   in earlier CAS or renew an old native/host anchor.
4. Inside the controller session lock, use only the already-persisted exact
   envelope and host-age check in `stage(intent=..., before_publish=...)`.
   Never perform HTTP/ADB/guard/session reentry there.

The generic mechanisms already exist: `NativeNavigationIO.bind_before_send`,
controller admission/`before_publish`, and the once-only OS input callback.
The Lifecycle Editor, Chat, Pending, Close, World and Restore callbacks already
own durable input/freshness responsibilities. The composition must extend
those exact owners with the phase check rather than replacing or adopting a
different owner's callback. Pending's final callback must preserve its original
intent/hold deadline and candidate guard. Background HOME/resume fences cannot
depend on an unavailable background Qt query. There is not yet an executed
Lifecycle-wide phase/transport join; this remains implementation work.

## Real budgets and stage bill

No universal aggregate 128 limit is invented. Preserve and report separately:

- the one old-process mutating World journal: at most 128 complete triples;
- the new-process Process observation history: 2 to 64 complete original
  UI/gesture/drive/native/presence/domain rows;
- Source3: at most 128 completed readonly samples, with complete new triple,
  Pending and NativeFeature originals; no fictional World frame index;
- each original container's 512-child/16 MiB unpacked-container limits, its logical raw
  budget, and each private file's 64 KiB limit; World/Process codecs retain
  their separate 48 KiB packed and 16 MiB raw/decoder bounds;
- unchanged per-call freshness, negative/quiet cadence and 120 s runner limit.

The measured Source3 prefix is World 2 before/after baseline, 19 after actual
Create/type/World/Back and its readonly negative wait, and 85 after the existing
remaining Pending prefix. It also owns 17 new readonly triples, 68 parts,
84,019 unpacked container bytes and 185,042 logical original bytes: 102 actual triples
in total. The older complete component run used 84 through Pending, plus Close
6, second World/release 15, normal Restore 7, Prepare 13 = 125 old-process
World triples, followed by 13 actual new-process triples. These are different
executions; adding the old remainder to 85 gives only a planning estimate of
126, not a demonstrated full coordinator count or fit.

The unchanged common waits have 54 samples as the hard count lower bound
(baseline, sixteen checkpoints, cleanup, at least three advances each). The
zero-query-latency nominal .25 s schedule is 104, not a real-world lower bound.
Source3's real count can differ with original acquisition time or stability
resets; actual Back required 14. Its full physical part/byte cost must be
measured, not extrapolated from 68 parts. No part count may omit the returned
native histories or original bundle fragments. Independent Actor acquisitions
are still unmeasured and cannot be reported as zero. See the detailed
[original budget audit](LIFECYCLE_QUERY_BUDGET.md).

## Restore, Actor, images and public boundaries

Action 16 currently prepares the original old process; actual controlled
shutdown/restart belongs to the existing Process/RestartInputs machinery.
Source3 still binds the original PID and live readers. It cannot poll that PID
after retirement or reconstruct a new live source from `Process.next.frames`.
The cleanup connection needs the real new binding/reader factories, original
PID/start absence, native process birth and lifecycle continuity, then a fresh
cleanup baseline using the unchanged common consumer. Actual Qt/resource
release must be observed; retained journal ownership is not a product resource
and does not by itself prove final file/host closure. Existing separate caps
and complete old/new originals survive that transition.

Every primary sample also needs the existing common consumer's new independent
Actor entry. No Lifecycle Actor worker/typed source/return-and-consumption join
is yet connected to this graph. It must independently acquire original facts
and preserve its own process/source/sequence identities; copying primary state
or passing a substitute witness to `Journey.execute()` is excluded.

The unchanged recipe requires images at 3, 7 and 16 and a changed image at 14.
There is no connected Lifecycle artifact provider proving those actual tablet/
world surfaces and their original PNG/camera/subject ownership. Existing
capture owners can be reused only with actual Lifecycle surface/source joins;
Browser DOM evidence or expected images cannot be renamed as Lifecycle proof.

There is no public `feature.lifecycle-input.act/cleanup` route or advertised
capability. The private phase-fenced dispatcher now executes actions 1 to 4
with actual Source3/common wait checkpoints and the same World/Restore graph;
its same-class continuation now reaches action 7. Extend that
dispatcher through 16 with the table above after its real owner/fence counters
pass. A whole run must wait for the concrete complete operation/source graph;
public qualification additionally needs independent Actor, image provenance,
cleanup/resource/file/archive/host finalization and actual True-hook evidence.

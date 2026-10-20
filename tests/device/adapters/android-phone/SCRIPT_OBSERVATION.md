# Durable five-source Script observations, version 1

`_script_observation(selector, run, fixture_url, role=..., fixture_state=...,
retired_owner=...)` composes the existing original-source readers, four-source
history and file/resource join. It returns `PhoneScriptObservation`, with
`read(ticket, after_epoch, after_sequence=None)`. Roles remain `primary` and
`actor`; their history and observation journals are separate. The native-command
transport always uses existing-session/read-only admission. No publisher token,
expected state, verb, measured count or requested existence is accepted.

Factory admission reads only SDK/process/installed-candidate metadata. It sends
no file, execution, UI, service or lifecycle observation request. The initial
native directory is deliberately unknown until an original file query supplies
it during the first sealed acquisition. The journal binds original context,
run, role and fixture URL. A completed record additionally retains the actual
directory and original advancing file cursor. Changed contexts, foreign scopes,
unsupported versions and interrupted records cannot be implicitly adopted.

The exact private record is `sourceObservationVersion:1`,
`sourceKind:"phone-script-observation"`, `binding`, `runId`, `role`, `directory`,
`fixtureUrl`, `phase`, `sequence`, `fileCursor`. The existing private parent,
mode-0600, single-link, no-symlink, atomic replace and 64 KiB cap are unchanged.
The observation sequence is a count of sealed acquisitions, not a native
function/event count. A future caller cursor fails before any source request;
a lower cursor after a lost result triggers a separate fresh acquisition.

The whole read holds the stable Script source lock, persists `phase:"reading"`
first, then constructs and restores the four-source reader under that same lock.
It checks the factory's actual file packet against the previously persisted
cursor before another source can hide its counter/clock rollback. The live
reader acquires a second original file packet and four new original sources.
Native file reads additionally retain a nonregressing original capture clock
within the getter instance. The final file join advances from the admission
cursor, requires the original native birth/PID/scope/bytes, folds all five clocks
into the oldest capture, and derives the actual physical resource inventory.

Only successful source acquisition, matching original recomposition and a
persisted final cursor return to `ready`. The whole operation, including lock
wait, factory construction, history replay, source/clock reads and private writes,
is bounded to 20 seconds; individual SDK/getter/runner limits remain. The same
process/thread may explicitly share one held lock instance through factory and
reader layers. Other instances, roles, threads and processes cannot inherit that
owner; the existing OS lock still excludes them. Locked reads assert ownership.

A failed final write may leave the four-source transcript advanced while this
record remains pending. Recreating the observer cannot drop that uncertainty or
reset the old file cursor into success. A lost final write return can leave a
complete `ready` cursor: that call still fails, and reconstruction performs a new
fresh acquisition. Stale objects cannot overwrite another invocation's record.
Ignored requests, changed installed bytes, rewound original clocks, replayed
counters, wrong births and missing source data never become empty resources.
General Phone cleanup still executes base teardown and refuses success while
any original observation journal remains. There is no unconditional reset or
discard operation.

The private result contains `sourceObservationVersion:1`, `sequence`,
`fileScopeVersion:1`, `measurement`, `resources`, `fileCursor`. Measurements remain
original execution/code/module/effect/UI/service/lifecycle values, with the oldest
of five source clocks. Raw native metadata stays private. The coordinator must
use these values in the existing v16 observation shape; it must not publish
this private object directly or copy primary facts to the actor.

Thirteen Phone integration cases cover reconstruction, file counter/clock
rollback at admission, future cursors, failed/lost persistence, stale objects,
ignored file requests, role separation, original reserve/stage/release baseline
continuity, whole deadlines, candidate changes and incomplete-cleanup rejection.
Three additional source-lock cases cover explicit nested ownership, missing
ownership and another thread; cross-process exclusion remains tested. Native
file-source cases additionally reject within-instance clock rollback. All are
host simulations; C++ is uncompiled and devices remain untested.

This completes the internal five-source observation transaction for one original
process. It does not yet implement the full nineteen-step feature coordinator,
its pre-input/load barriers and readiness, original HTTP404 join, explicit
per-role restart-history handoff, independently running publisher or complete
verified cleanup. Those must be wired before advertising `feature.scripts.*`.
No full feature capability, product pass or physical acceptance is promoted.

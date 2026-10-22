# Phone Snapshot observer admission, version 8

The existing `script_observer.py` entry point adds Snapshots through its closed
version-8 configuration. Its exact fields are `featureObserverVersion` (integer
8), `area` (`snapshots`), `target`, `candidateArguments`, `fixtureUrl`, `actorToken`
and `durationSeconds` (30–1800). The target and complete candidate arguments must
pin the same installed artifact, inputs, source, version and existing SDK session
as the primary owner. The original candidate verifier still validates every
required argument before constructing an adapter. Configuration files use the
existing private state reader; credentials and target selectors stay private.

The actor has its separate fixture token. A primary reader token in its process
environment is refused before candidate admission. Expected state, image policy,
primary/control credentials, alternate target and unknown configuration fields
are rejected. All fourteen complete public feature flags are forced off before
constructing the observer adapter, including Chat, Avatar/People and Snapshots.
Only internal independently acquiring actor factories are used.

`run_snapshots` waits for the actual `snapshots_feature_store` owner with the
exact run URL, constructs `_snapshots_actor(target, run, client=actor_client)`
once, and calls its `step()` method. A successful observer exit requires an
actual boolean `True` from that independently retiring actor. Missing owners,
foreign run URLs, source failures, missing retirement, clock regression and a
step finishing after the observer deadline remain failures. Busy source locks
are polled without constructing another actor or publishing a second input.
The actor owns its own sources, originals, evidence and lifetime; this dispatch
never calls primary `feature.snapshots.observe` or any primary input operation.

Historical grammars remain closed: v2 has Scripts/Authentication/Graphics; v3
adds Emotes, both Web areas, Navigation and Audio; v4 adds Create and Avatar/People;
v5 adds Assets; v6 adds Chat; v7 adds Lifecycle/Input; only v8 adds Snapshots.
Emote image policy remains mandatory for v3–v8. A separate Avatar peer target and
peer image policy remain mandatory for v4–v8. Old versions cannot claim newer
areas, and the legacy Script-only version-1 grammar is unchanged.

Nine targeted source/entry-point tests pass, covering every area/version pair,
unknown/privileged fields, missing and foreign ownership, busy/failed/slow actor
steps, non-boolean retirement, clock regression and bootstrap credential/flag
isolation. Thirteen existing registration/observer tests also pass across Create,
Assets, Lifecycle/Input, Chat and Avatar/People. Their explicit synthetic actor,
clock and candidate boundaries qualify dispatch/admission logic only. Full
Snapshot source composition must supply the named actor factories before this
area can run; this packet enables no public capability. No product function,
complete Android build or device acceptance is established by these checks.

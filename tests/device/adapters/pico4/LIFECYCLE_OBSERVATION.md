# Lifecycle primary observations (private, partial)

This documents the original v1 packet and its measured evidence. The staged
pre-input v2 entry and subsequent continuity fix are described in
[Lifecycle baseline](LIFECYCLE_BASELINE.md).

`PicoLifecycleObservation` connects fresh observations to the existing
Create/Chat/background/Pending/Close/Restore process chain. It has no input
authority. `_lifecycle_observation_owner` accepts those actual live owners in
the canonical namespace and reuses their exact World, PID, binding and source
lock. It creates no native reader, default Script inventory or input route.
The factory and orphan cleanup guard are present; the new factory has not yet
received a separate canonical-factory test on this branch.

Each `read(after_sequence=N)` requires the current live cursor at exactly N,
then acquires a new World UI/gesture/drive triple, an original Pending response
and an original NativeFeature response. Generation comes from matching the
current native editor ID against the original Create, Chat and two Scripts IDs
bound by the existing owners. Requested phases, caller generations and requested
effects are not observation sources. World attempts use original consumed
gesture events; stale attempts use original rejected context-retired events.

The private root is `lifecycle-primary-observation.json`, version1. It retains
scope, `phase=reading`, complete immutable chunk inventory, ordered bundle
references, completed record indices and an unresolved read intent. The intent
precedes World acquisition. The full Pending original/request is durable before
the Native query; the full Native original is durable before projection.
Result bundles bind the exact World index/hash, those two original bundles and
current owner journal hashes. Existing lossless source bundles/chunks retain
their full physical, order, SHA, raw-byte, 512-part/16-MiB and private-file
checks. This is additional evidence storage, never another World frame budget.
Every acquisition still consumes the original World128 limit.

After result construction and persistence, both inside and after the real
source-lock exit, the reader checks physical roots/children, the original owner
graph, installation/PID guards, all three native clocks and Host monotonic time
against the same oldest original epoch. The age remains1500ms, future allowance
250ms and call budget20s. No later query refreshes the earlier originals. Any
failure latches the cursor, retains landed/unresolved files and forbids another
acquisition. A new reader cannot adopt historical files as a live cursor.

`resources` describes actual retained Qt editor objects and native Pending
runs, including non-current contexts. Private Host evidence files are separately
owned, orphan-guarded and retained for post-baseline archival; their presence is
not a product-created file. The two pure projection tests exercise that
distinction without native reads. Empty product resources never qualify Host
file/descriptor finalization.

## Actual evidence and boundaries

All paths below are beneath the private evidence directory
`/home/user/tmp/overte-pico-lifecycle-continuation-20261024-sCdPTg8o`.

The new positive passed1/25.341s in `observation-positive.log`:
two fresh Scripts-generation4 samples followed by the unchanged existing normal
Close, second World action/release, Location-only Restore, Prepare and
Process-v2 Restart positive. The same authoritative World finishes at **127/128
frames**; no frame was omitted or put in a second counter. The old-PID reader
then refuses another acquisition. Originals are retained from construction at
`lifecycle-editor-8pq8jexx`. Full checkout13469-file manifests before/after are
identical, SHA
`ce5b83dd85d50e55f1c0cff53a9e420008433794678573d0d622d3cbbc823470`.

Three disjoint counters passed3/34.158s, same source manifest:

- actual outermost source-lock exit failure after successful inner reads:
  `lifecycle-editor-zc2mtczw`;
- landed completed-record CAS followed by Native+2000ms at fixed Host time:
  `lifecycle-editor-umpx_0og`;
- original128-frame cap: `lifecycle-editor-8_pho5q2`.

The last counter initially used exceptions as source spies. Because the runtime
sanitizes inner exceptions, that alone was insufficient proof of zero calls.
The corrected test explicitly records all Capture/Read/Send calls and requires
`calls==[]`. Only this test was repeated:1/11.748s green,
`observation-cap-corrected.log`, originals `lifecycle-editor-kvnpb830`, unchanged
full manifest
`d4a4f51b2fc61161899ff67664a4701086fcf93522ee04511a9cc0838bf47b0d`.
This manifest also contains the new pure product-resource projection; the prior
positive/counters belong to their earlier manifest, not a relabeled final run.

All Qt/input/physics/domain/OS observations retain the existing explicit model
seams. These are actual Python owner/storage/clock/session integration results,
not devices, a common `Journey.execute`, an independent Actor, images or public
Lifecycle acceptance. Public capability remains disabled. Retained source roots,
chunks, journals and Host handles still require independent finalization.

The original v1 constructor accepts the already-created complete owner graph; its
positive proves fresh observations after Pending, not a pre-input baseline.
The following v2 packet supplies a staged live constructor/attachment that can
observe the original baseline before Create without installing the later
Scripts input callback prematurely. Common v16 still requires all16 actions,
at least three advancing samples per checkpoint and actual3s negative/cleanup
windows. Those actual queries must fit the same128; the measured127-frame
private positive gives no permission to reset it, cut cadence or replay old
frames as fresh. Public dispatch, independent Actor, actual image provenance
and the external cleanup-baseline/return/archive/Host closure remain open.

## Review and registration

Dependency: `9cb02f4b189117f965a1fbf2092a17cb62ab9c24`, following
`84d122721b2c8380017ed2bf12a8ac1ba5490264`. Do not reselect dependency-only
`1c85b265eb1a6a37c14afb0fce0ca5178bab7d1b` into Root.

The initial packet added `pico-lifecycle-primary-observation`, current1/reads1;
the later baseline packet versions that entry to2/reads1,2.
Initial selector: `lifecycle-primary-observation`, unchanged120s budget; six distinct
cases (one new path positive, three faults, two pure resource projections).
One shared control-plane module pattern. The existing Pico risk rows gain this
selector additively. Local catalog231→232; integration must add one to Root's
own current count instead of copying this branch's total. No unchanged full
positive is repeated by the new wrapper through an imported fixture class.

Final checks: both new pure resource projections passed2/0.000s; shared and
Pico-wrapper discovery each finds exactly six cases. Registry validation is
coherent, Coverage10/0.036s maps14/14 risks, and the four repository suites
(`documentation-contracts`, `project-coverage`, `documentation`, `source-layout`)
passed in2.63s. `git diff --check` passed. These checks did not repeat the
positive or the other fault cases; see their separate manifests above.

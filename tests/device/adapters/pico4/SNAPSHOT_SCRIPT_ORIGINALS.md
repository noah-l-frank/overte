# Original Snapshot VM events on Pico

This is a private source component, not a Snapshot capability or a completed
cancel recipe. It retains the current common v16 journey and the existing Pico
VR input. It sends no capture, cancel, event kind, timer, caller, manager,
compilation, source digest or desired state to the observer.

## Fixed provenance

The recorder, strict history decoder, actual `featureCaptureWorkObservation`
body and eight observation-only Snapshot JS additions are selected from fixed
Phone `5527d540e99cc6dba4204a5e904a854e6e1cd2b4`, originating in
`443448a697d466ba70fe3571830697e62758f41f`. The neutral recorder is named
`SnapshotScriptHistory`; it has no Phone UI or Android-owned include. The
existing reviewed ScriptWork v2 core is the local dependency described in
[the reuse review](SNAPSHOT_PHONE_REUSE_20261022.md), not a second integration
packet. Phone's common v18 facade, touch driver and mono pixel proofs are not
selected.

Under `OVERTE_E2E_FEATURE_TESTS` plus actual `--testScript`, the original V8
method boundary obtains the current compiled function's script ID. The actual
manager thread records its assigned manager, submitted code, V8 compilation,
active original timer handles/intervals and per-function callback activity.
`Snapshot.featureCaptureEvent` accepts the product's actual kind/request/mode/
revision and obtains caller provenance from that native scope; no supplied
caller DTO is accepted. The ordinary pending observer runs after the actual
350-ms and 60-s timers are registered. The ordinary cancellation observer runs
after their actual clearing. Idle cancel and foreign/late status callbacks do
not create events. Product timing, arguments and decisions stay unchanged.

The recorder holds at most 256 immutable events. Invalid original caller data,
clock regression or overflow makes it permanently incomplete. It does not
reset, truncate or synthesize an idle history. No native Snapshot request is
inferred from a pre-render Script event.

## Existing private transport

`PicoBoundAdapter._snapshot_script_originals(target, source_lock=...)` reuses
the exact parent `ScriptJourney` source-lock object and existing bound native
transport. The command is exactly `schemaVersion`, `action`, `commandId`,
`runId`, with action `feature-snapshot-script-originals`. It cannot perform a
capture/cancel or reset the recorder. The original TSI getter requires the
started private lifecycle, real Pico HMD, current test process, private output
directory, an already existing Snapshot dependency and the existing bounded
weak owner-thread queue. Non-Pico TSI returns unavailable. `saveObject` admits
the private `feature-snapshot-script-originals.json` result through the existing
private writer; root's closed feature-result admission also handles it.

The native query fixes the first run, rejects reused query IDs and stops after
4096 IDs. It publishes actual PID, monotonically increasing query sequence,
wall time and complete immutable history; raw output is limited to 64 KiB.
Missing/oversize history is unavailable. The reader publishes each query once,
polls its result without resending and preserves original raw bytes plus SHA.
It checks the final native clock and host monotonic age after copies and the
last original guard. Cold `restore()` supplies history continuity, never
freshness. New input is not delivered by this source.

`join_compilation` is an additional required join before a VM event can qualify
the future cancel owner: a separately read actual native Script observation
must contain exactly one running original manager and identical compilation,
manager membership and submitted code. Its exact installed Snapshot URL must
come from the independent installed script-root owner. The compiled UTF-16
code units and digest must match `snapshot-script-pin.v1.json`, generated from
the selected reviewed Snapshot JS source. A URL/basename or a matching request
alone is insufficient. The pure join's historical DTO validation does not
replace the owning flow's current source-age, process, phase or UI fences.

## Verification and remaining work

`device/test_snapshot_script_originals.py` contains the owning pure/factory/
Probe cases. Its native child check compiles original manager caller-scope,
work lookup, Snapshot bridge/query and recorder bodies against real Qt timers,
clocks and thread identity. VM manager/source identities in that host compiler
check are explicit synthetic boundaries; it does not compile V8, a whole
ScriptManager translation unit, an APK or run a device. The existing native
Snapshot originals compiler additionally compiles and executes both actual
Pico/non-Pico TSI getter bodies with real private lifecycle and queue behavior.
The production Snapshot JS tests exercise the actual ordinary capture/cancel
handlers with explicit fake Script/native service boundaries.

The fixed passive original Review source is now selected on the actual Pico
3D TabletRoot in [its separate packet](SNAPSHOT_REVIEW_ORIGINALS.md). Next, bind
the existing fixed Phone FastCancel recipe to the current Pico normal controls. No second cancel/timer system is introduced. Actual
pre-render normal cancellation, immutable original file scope/FD retirement,
all thirteen typed settings, three-second Script/Qt/native cleanup,
permission/Documents/receiver/upload operations, stereo and panorama fidelity
and an independent actor are still unqualified. All existing Still/source
journals and files remain owned; nothing here retires them or changes cleanup.

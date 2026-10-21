# Pico Script feature binding v1

The existing bound Android/Pico entrypoint implements the complete v16
`feature.scripts.act`, `feature.scripts.observe`, `feature.scripts.cleanup`
triple. This is **source implementation and host simulation only**. Native
instrumentation is uncompiled, devices are untested, and no build, installation,
ADB/Appium/OpenXR device run or Jenkins job was performed.

The [fourteen-area matrix](FEATURE_COVERAGE_20261021.json) is current for this
isolated branch. Scripts is the only complete Pico source-level area here. The
remaining thirteen complete triples remain unavailable, so a required full run
cannot become green. Earlier [status entries](FEATURE_ADAPTER_STATUS.md) are
historical component checkpoints.

## Architecture and original Pico input

The existing path remains catalog module → `OverteSession` → bound adapter →
Pico automation. `PicoScriptJourney` supplies concrete Pico factories to the
shared [Script coordinator](../script_journey/feature.py). Its
[provenance manifest](../script_journey/PROVENANCE.json) pins the frozen Phone
source at `fe4684bf46585088370b3a328a738f147e670b97`. No uncommitted Phone work,
Phone Appium session, package identity, coordinates or monoscopic captures were
imported. Shared prerequisites have a separate
[reviewed selection manifest](STABLE_PHONE_SELECTION.json).

Ordinary inputs use the existing `PicoScriptIO`/`PicoNavigation` implementation:
OpenXR left-secondary Tablet open/close, actual VR MENU → Edit → Running
Scripts, actual From File/From URL dialogs, original current control/source
UUIDs, native VR surface pointer delivery and `NativeFieldInput` IME/keys. No
Script service, QML signal/handler or observed property setter performs input.
The source observer has no pointer/key/controller input authority.

| v16 operation/verb | Ordinary input and independent required effect |
| --- | --- |
| Observe before input | Reserve host cleanup intent; locate the actual absent native directory without creating files or opening UI |
| `open` | Stage the four original owned files exactly once, then open the actual VR manager |
| `picker-open`, `picker-cancel` | Normal From File/cancel; separately observe actual whole-tree picker state and unchanged execution |
| `picker-accept` | Normal folder/row/companion review/primary/Use Files input; actual successful callback, exact submitted UTF16 code, uncached relative CommonJS module and advancing owned Box effect |
| `stop-owned` | Normal exact full-URL Stop row; actual complete all-known manager/engine/module/effect absence |
| `restart-app` | Original one-send Android stop/launch and OpenXR binding; old-PID ESRCH, actual new native birth/counters, unchanged original files, closed/empty UI/execution for three seconds |
| `load-url` | Normal From URL; exactly one real owned HTTP404 receipt, original native NotFound callback and separately visible matching full-URL error |
| `close` | Normal cancel/Home/Tablet close; current whole-tree UI absence, not an ACK |
| Cleanup | Ordinary Stop/cancel/close, actual quiet absence, separately verified file release; a second cleanup reads again without restaging |

`await`/expected state is never an input to observers. The complete nineteen
checkpoints and six measured fields remain owned by the unchanged
[shared v16 source contract](../../feature_journeys/SCRIPTS_SOURCE.md).

## Five original sources and two roles

Every accepted observation independently acquires:

1. Original native fixture location/bytes/owner and its original source cursor.
2. Actual engine/code/CommonJS/effect/load-result and all-known-manager history.
3. Passive original manager/picker inventory from the real Pico
   `TabletProxy::getTabletRoot()` and offscreen VR window.
4. Separately acquired original running-Script service rows.
5. Actual persisted native lifecycle counters and process birth.

The new native read is compiled only with `OVERTE_E2E_FEATURE_TESTS` and also
requires the existing dedicated test-script bridge. The fixed
`script-file-ui-command.json` accepts exactly
`{schemaVersion:1, commandId:<32hex>, action:"observe"}`. The GUI timer captures
`script-file-ui.json` once for a new nonce. Repeated commands do not reacquire or
retime a completed nonce. The native source retains up to 4096 original nonces
per process and rejects prior identities even after another role has read.
Historical source transcripts separately reject reused execution/UI/lifecycle
query identities despite otherwise advancing cursors. Shared whole-tree inventory includes hidden objects;
modal input suppression cannot conceal a surviving picker or manager.
Retained native panels remain owned resources even while the tablet is hidden;
cleanup must observe their actual retirement before releasing files.
`tabletPresent` and `tabletShown` come from the real TabletProxy. Missing,
ambiguous, partial, foreign-thread or unavailable trees fail rather than become
an empty inventory. The native source never opens a tablet to repair a read.

The original candidate verifier, installed APK byte hash, target/configuration,
PID/start, foreground and existing OpenXR host nonce journal guard every source.
Read factories cannot launch, activate, rotate a nonce, submit a grant, change
files or deliver UI input. The separately documented
[restart binding recovery](SCRIPT_RESTART_BINDING.md) is the only observation-led
recovery for an already-issued uncertain launch. It proves native birth/counters
and kernel old-PID death before restoring only the original host binding. The
failed delivery call remains failed; no stop/launch is resent.

Primary and actor retain separate original source transcripts, cursors and
observation journals under one private per-target source lock. Each role must
have independently observed the pre-restart engine/effect and independently
query old-PID death in the new source. The actor never calls primary Observe or
copies its normalized facts. A source downgrade, reused cursor, missing result,
wrong provider, stale sample, foreign process/code/bytes or changed historical
prefix fails with original ownership retained.

## Future lab configuration

These are handoff instructions, not authorization to start services or contact a
device during this local task. Use only the Proxmox laboratory and official
`overte-jenkins` wrapper when a later task authorizes qualification.

The primary requires `OVERTE_PICO_FEATURE_SCRIPTS=1`, the existing
`OVERTE_PICO_NORMAL_SCRIPTS=1`, isolated debug/OpenXR configuration and all
existing verified-candidate arguments. `OVERTE_PICO_FEATURE_FIXTURE_CONFIG`
points to the private
[adapter-only read configuration](../../feature_journeys/ADAPTER_FIXTURE_ACCESS.md).
Its canonical parent is 0700 and its regular, single-link file is 0600. The
optional `OVERTE_E2E_FEATURE_FIXTURE_URL` must match it. Configuration parsing
performs no network or device action. Incomplete configuration fails; the
runner reader token is forbidden in the adapter environment.

The existing fixture server needs three distinct private credentials:
reader, actor and adapter. The adapter can read only original input/provider
metadata, cannot register/activate/retire a run, cannot publish, and cannot read
peer facts. The runner retains assertion/image policy and the reader token.
No token, selector, candidate path or original account data belongs in Git.

The separately managed publisher is
`tests/device/adapters/pico4/script_observer.py --config <private-config>`.
Its exact private configuration is:

```json
{
  "picoScriptObserverVersion": 1,
  "target": "<private Proxmox target>",
  "candidateArguments": ["<complete original Pico candidate flag/value arguments>"],
  "fixtureUrl": "http://<owned fixture>/feature-fixture/v1",
  "actorToken": "<independent publisher credential>",
  "durationSeconds": 1800
}
```

The original Pico parser and verifier admit the selected candidate. The worker
uses one explicit target and never discovers, launches, repairs or submits
input. It disables its own feature advertisement, waits only for genuine lock
contention/pending input, publishes fresh independently acquired facts and ends
after observed cleanup/retirement. Other source failures are fatal. The whole
worker is bounded to 30–1800 seconds. Its process and private configuration must
be owned, monitored and stopped by the future Proxmox run owner.

## Time limits, privacy and release

No source timeout was widened. Native getters retain five seconds/51 reads;
input/preparation is bounded to thirty seconds; readiness is bounded to twenty
seconds/64 original acquisitions with 250 ms pending intervals. Shared phase
waits retain twenty seconds/81 reads, at least three samples over 0.5 seconds,
1.5-second sample age and 250 ms future tolerance. Failure, cancellation, stopped
execution and restart/cleanup require three seconds. Cleanup independently
checks both host monotonic and original native epoch progress.

Input intent and the pre-input native barrier are durable before delivery.
Lost/uncertain ordinary inputs remain issued and cannot be retried. Original
files survive restart without restaging. Live callback/manager membership must
actually drain before release; a missing public row alone cannot prove it.
The full coordinator preserves old/new process stages and native absence
tombstones, including completed callback history.

After normal Stop/Cancel/Close, quiet execution/UI absence must precede file
release. Release ACK alone is insufficient: new original file-location and
five-source reads must prove actual absence. Both roles retain their journals
through the runner's final baseline. Adapter-wide cleanup finalizes only after
both original independent cleanup observations and another native absence read.
Its source-only retirement reader has no HTTP credential or network authority.
A hash-bound fixed-name retirement plan resumes interrupted host removal only
for unchanged originals. Source journals retire before the main owner; the plan
retires last. Residual or unknown journals prevent green cleanup. Original base
application teardown is attempted even when feature cleanup fails.

## Host verification and limits

The mandatory `script-feature-journey` and `script-feature-engine` catalog
groups select separate TestCases in `test_script_journey.py`; both remain in
the full catalog. Splitting their host execution preserves all assertions and
the existing 120-second per-group default. The unsplit group was measured at
125 seconds during local verification. No adapter/journey bound was widened.
The combined cases exercise the actual bound Pico wrapper, shared
coordinator, nineteen-checkpoint shared engine, separate actor, original temp
files and real loopback HTTP404. SDK, GUI, OpenXR, native engine/lifecycle and
candidate-tool responses are explicit synthetic boundaries. Counterexamples
cover consumed ACK with ignored input, forbidden resend, stale/foreign/partial
sources, candidate replacement, ignored original-file release and uncertain
launch recovery without another stop/launch or file stage.

The shared source tests additionally cover original code/module/manager identity,
immutable historical callbacks, file provenance, lost source results, reused
cursors, lock replacement/contention, partial private writes and interrupted
cleanup. Worker tests cover private configuration, bounded pending waits and
fatal invalid originals. These establish adapter/test logic only. Native build,
VR controller/ray/keyboard behavior, timing, rendering and physical acceptance
remain explicitly unqualified.

# Android Phone Script feature, owner and observer version 1

The existing Phone Appium entrypoint now implements all three v17 operations:
`feature.scripts.act`, `feature.scripts.observe`, `feature.scripts.cleanup`.
Enable them explicitly with `OVERTE_PHONE_FEATURE_SCRIPTS=1`, the existing
`OVERTE_PHONE_NORMAL_SCRIPTS=1`, a verified debug candidate and the existing
`OVERTE_PHONE_FEATURE_FIXTURE_CONFIG` private adapter access file. See the
[separate read-only credential contract](../../feature_journeys/ADAPTER_FIXTURE_ACCESS.md).
An optional `OVERTE_E2E_FEATURE_FIXTURE_URL` must match that file; the runner
reader token remains unavailable to adapter processes.
An incomplete configuration fails. Authentication is separately available under
its [own explicit configuration](AUTHENTICATION_FEATURE.md); eleven other
complete area triples remain absent; [Graphics](GRAPHICS_FEATURE.md) is separately available.
No acceptance policy or required-capability gate is weakened.

This is source implementation with device-free control verification. Native
instrumentation is uncompiled. No APK execution, build, installation, hardware
test or Jenkins run was performed. Proxmox qualification remains separate.

## Ordinary input and evidence

`PhoneScriptFeature` composes the existing normal Script action owner and durable
five-source observer. Preparation reserves host cleanup intent and acquires the
actual absent native directory; it neither stages files nor opens the manager.
The first normal Open stages the four controlled originals once. Every input
retains its original native pre-input barrier before delivery. Uncertain ordinary
input is never replayed; only the explicit one-send restart protocol can resume
from its original persisted OS/native proof.

The action is matched to the runner's actual active fixture ticket and closed
stimulus inventory. The adapter never registers, activates or advances a run.
Bounded readiness acquires new native source packets, persists each original,
and checks actual callbacks, submitted UTF16 code identity, real noncached
CommonJS completion, all-known manager membership and initialized local Box
effects together. A callback from another manager/generation, pre-input callback,
wrong code, ignored import, missing result or stalled effect cannot qualify.
The limit is 64 acquisitions / 20 seconds, with 250 ms pending intervals. The
existing 30-second input/preparation and native getter bounds also remain.

Each public observation obtains five new original sources under the source lock:
fixture bytes/location, native engines/code/modules/effects/load/membership,
passive actual manager/picker inventory, independent running-Script service and
native lifecycle. Their original oldest capture supplies the public timestamp;
actual resources supply the inventory. Durable observation v2 retains the actual
file packet as well as its cursor; no old v1 journal is silently upgraded.

`ScriptFixtureReader` attaches to the existing run with fresh read nonces,
immutable original HTTP history and pinned provider identity. NotFound requires
the actual native failure callback, independently visible current full-URL error
and exactly one original owned HTTP404 receipt after the input barrier. Wrong
authority, wrong body/status, foreign ticket, missing receipt or provider change
fails. A second active-ticket read after acquisition prevents relabelling an old
sample. An actor drops a retired sample while retaining its accepted cursors.

Normal mobile stop/start can record additional actual Hidden/Suspended/Active
events. The common Script restart check requires exactly one additional launch,
at least the required activation, nonregressing original counters and a stable
three-second window. It does not rewrite counts to expected increments. Missing
launch/activation, regressing or continuously changing counters fail.

## Restart and independent actor

Stage 0 retains each role's original history/observation files. Stage 1 uses
separate `-restart` files and is authorized only after the normal persisted
restart protocol, preserved original files and actual old-process ESRCH proof.
Each role must itself have observed the original pre-restart bundle engine and
effect; the role independently queries kernel exit in the new process. Matching
old engine/effect identities, original bindings and new native counters are
required. New startup must remain empty, closed and without owned load callbacks;
the owner never autoloads or reopens. Reopen/cancel/reimport use normal controls.

`script_observer.py --config <private-config>` is a separately launched publisher.
It receives only its actor credential and the same reviewed candidate arguments.
The config and parent must satisfy the existing private-file rules (0600 file,
0700 canonical parent, no symlinks/shared links). Exact fields are:

```json
{
  "scriptObserverVersion": 1,
  "target": "<private configured selector>",
  "candidateArguments": ["<the complete existing candidate flag/value arguments>"],
  "fixtureUrl": "http://<owned fixture>/feature-fixture/v1",
  "actorToken": "<separate private publisher credential>",
  "durationSeconds": 1800
}
```

The original verified-candidate parser/verifier validates those arguments before
target use. Do not supply a reader token to that process; an inherited reader
token is rejected. Its own feature advertisement is disabled. It waits for the
owned run journal, constructs a separate actor reader and acquires five new
original sources per sample. It never calls primary Observe, copies primary
facts, repairs a session, launches an app or submits feature input. Only genuine
lock contention and pending input phases can wait. Other errors fail. Publication
uses advancing actor sequence, original capture and all six measured Script
fields. Reader credentials cannot publish. Retired samples are dropped without
retiming, and original fixture retirement after observed cleanup ends the worker.
The whole worker is bounded to 30–1800 seconds. The later Proxmox run owner must
start/monitor/stop this process with its private configuration; host self-tests
never launch it against hardware. No workstation device runner is enabled.

## Cleanup and interrupted host retirement

Feature Cleanup cancels an owned picker/dialog, stops owned execution via normal
controls and closes owned UI. Pending missing-URL work needs its actual callback
before retirement. New original all-known manager/engine/module/effect absence,
closed UI and no new owned callbacks must remain quiet for three seconds in both
host and native clock domains. Original files are released only afterward and a
separate five-source read must prove actual native absence. A second Cleanup
performs another independent absence read without restaging or a repeated release.
An ignored stop/release or a residual Box/picker remains a cleanup failure.

The owner retains all journals through the runner's final baseline and actor
observations. Adapter-wide cleanup retires them only after both roles' own
current-ticket cleanup observations, original file absence and another fresh
five-source check. The restart-input owner also requires its current native
proof before retirement. A bounded private retirement plan pins exact hashes of
the known journal filenames. Interrupted removal may continue only for those
exact records; changed/foreign records fail. Every continuation rechecks actual
native absence. Source journals are retired before the main owner, and the plan
is removed last. Base app/session teardown still runs after feature failure;
unresolved ownership prevents green cleanup.

Host counterexamples cover ordinary inputs, two original readers, all nineteen
shared steps, real loopback HTTP404, missing/foreign evidence, ignored inputs,
per-role restart lineage, cleanup and lost retirement returns. Simulations prove
the test/adapter control logic only; they do not establish product function.

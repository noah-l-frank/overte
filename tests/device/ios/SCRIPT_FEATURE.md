# Source-level iOS Script adapter

The canonical physical candidate adapter implements `feature.scripts.act`,
`feature.scripts.observe`, and `feature.scripts.cleanup`. The unchanged shared
v16 nineteen-step journey has a complete host regression using ordinary iOS
W3C controls, the original HTTP/AFC transports, real temporary companion files,
an actual loopback 404 response, and separate primary/actor acquisitions.
Native and OS SDK execution in that regression is synthetic. Native compilation,
installation, Proxmox execution and device qualification remain unverified.

## Explicit admission and integration

Only the canonical `--native-binding --physical-candidate-metadata ...` entry
can admit the triple. The component and simulator adapters cannot qualify it.
Keep all existing physical-candidate arguments and the explicit
`ios-native-qt-scripts-v1` target profile. Set
`OVERTE_IOS_FEATURE_ADAPTER_CONFIG` to an absolute private mode-0600 file in a
mode-0700 directory with exactly:

```json
{"iosFeatureAdapterVersion":1,"areas":["scripts"],"fixtureConfig":"/private/adapter-reader.json"}
```

The separately protected fixture configuration uses the existing
`fixtureAdapterAccessVersion:1`, `fixtureUrl`, and `adapterToken` fields. That
credential can read provider/phase inputs but cannot see actor facts, register,
activate, publish or retire a run. An absent configuration advertises no triple;
a malformed one fails admission. The installed source gate remains mandatory.

The laboratory must separately start `script_observer.py --config <private-file>`.
This source addition does not start it or modify laboratory configuration.
Its exact config fields are `iosScriptObserverVersion:1`, `target`,
`candidateArguments`, `fixtureUrl`, `actorToken`, and `durationSeconds` (30–1800).
`candidateArguments` contains the same frozen physical-candidate CLI inputs.
The worker rejects alternate action/platform/target/operation arguments, uses
its own actor credential and existing session, never invokes primary `observe`,
and never discovers, installs, launches or repairs a target. It exits on owned
retirement, failure or deadline; it does not silently switch runs.

## Input and independent effects

`IOSScriptRuntime` supplies full source/archive/session/generation/target/PID
bindings to the existing normal manager, file owner and restart controller.
It shares their original ownership files rather than creating parallel input
owners. Each input ticket is durably issued before ordinary input. A failed
receipt remains issued. Repeated ordinary tickets cannot resend input. Only
the existing explicit restart controller can resume from independently observed
old-PID death, new native birth/counters, installed bytes and first-probe proof.
Journal v4 retains v1/v2/v3 installed-code readers and component recovery scope.

Each role acquires five new sources: complete ScriptManager membership and
submitted UTF-16 code digests; actual consumed companion modules and advancing
entity ticks/color/user data; the original retained Qt manager/Label/picker
inventory; the independent native diagnostic Script list; native lifecycle and
actual fixture path/presence/bytes. Resource projection reflects physical
presence, including zero-tick effects. Missing/incomplete membership, foreign
source/process/candidate, changed bytes, pending system picker, mismatched Label,
unknown source aliases and replayed clocks/cursors fail instead of becoming
empty success. The missing-URL result joins actual native callback and displayed
failure to the server's serialized status, response identity and written bytes.
Neither a host GET alone nor an input ACK establishes client behavior.

## Clock domains and durable history

Native timestamps remain unchanged. A separately journalled, nonce-fenced native
read brackets each fresh five-source acquisition together with measured host
UTC/monotonic start/end. Both elapsed intervals must agree, all native envelope
clocks must lie within the fence, and the whole window stays below 1500 ms.
The public timestamp is the host acquisition start, independently retained from
the native measurement. A canonical digest binds every original source. History
reconstruction validates that exact join and source prefixes without IO; its
next result still requires five fresh originals. Failures retain reading intent.

Persistent callbacks must follow the original input barrier. They need not
follow every later sample fence: a legitimate 404 callback remains historical
while its displayed state is sampled over the three-second window. All newly
acquired source envelopes must still follow the current native fence. The
server receipt uses its own host activation clock and current immutable ticket.
No native epoch is compared to host HTTP time.

The shared journey keeps one actual launch and activation per restart. It also
accepts zero or one final original Hidden notification from the terminating
process, as supported by `FeatureLifecycle`; it preserves the measured value.
Additional launches/activations/backgrounds, regressions or a nonstable window
cannot pass. This is shared host assertion logic, without a public schema change.

## Cleanup, interruption and dependency reconciliation

Cleanup owns normal Stop/Cancel/Close, drains actual engines, known retained
managers, local effects and callbacks for three seconds in both native and
monotonic time, releases only the owned fixture tree, then reacquires actual
absence. Repeated cleanup performs fresh absence checks. Journal finalization
requires both roles' independently acquired cleanup frames, then another fresh
five-source check. A persisted hash/CAS retirement plan supports interrupted
host-file retirement; it never supplies product evidence. Installed-candidate
cleanup inputs permit finalization before normal SDK teardown. Lost candidate
inputs or a failed feature finalization still reach original teardown and retain
unresolved feature/installed ownership rather than reporting green.

Shared source dependencies are selected from frozen Phone
`fe4684bf46585088370b3a328a738f147e670b97`: membership/root/location/handoff packet
in local commit `a89bf69a02`; provider packet
`b94541635b15d39fc1eea86414391495feef246e`; pure measurement/history/file-scope/
serialization/causality/input logic now under `adapters/script_feature/`.
The iOS coordinator adapts the frozen coordinator to actual iOS controls and
separate clocks. No Android process, ADB, package, permission or file transport
is used. Reconciliation must preserve the adapter-only reader authorization,
all installed v4 legacy readers, current shared v16 inventory, and the original
Phone/Pico journals and transport semantics. No reference worktree was edited.

## Local verification checkpoint

The no-build selection passed 484 iOS and 1,037 shared cases, with no failures,
errors, skips or blocked native/compiler/device attempts. Three shared native
compiler cases and twenty iOS compiler cases were explicitly excluded before
execution, rather than reported as passed or skipped. The five selected project
suites (documentation, documentation contracts, iOS input selection, policy
consistency and project coverage) also passed. Additional small regressions
cover exact v3/v4 proof separation and pathlib configuration input.

Only Scripts is completed by this packet. The other thirteen feature adapters
remain active implementation work in this isolated branch.

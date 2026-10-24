# Normal Running Scripts URL lifecycle

`scripts-management-parity` opens the ordinary Running Scripts UI, loads an owned
URL, restarts it, stops it, loads it again, stops it again and attempts an owned
HTTP404 source. This is locally tested scenario logic. No native adapter yet
advertises its new actions, and no device acceptance is recorded.

The native adapter must explicitly implement these closed actions:

- `scripts.manager.open`: open the ordinary Running Scripts panel.
- `scripts.load-url`: use From URL, its actual text dialog and ordinary consent.
  The source is one owned fixture URL; a missing source is an intentional test.
- `scripts.restart`: activate the matching owned row's Restart control.
- `scripts.stop`: activate the matching owned row's Stop control. Be idempotent
  when the owned row is absent. Never use Stop All or stop unrelated scripts.
- `scripts.manager.close`: dismiss only the owned panel/dialogs after partial
  failures as well as successful runs.

Actions return only `performed: true`. Do not invoke ScriptDiscoveryService,
load a probe command, inject a bridge message or manufacture a script event.
Native activation must separately qualify the real platform controls.

## Owned fixture and private observer

Start `python3 tests/device/fixture/script_management.py --bind 0.0.0.0
--public-host <reachable-lab-host> --ready-file <private-environment.json>`.
The ready file has mode0600 and the existing fixture-environment schema. Supply
it through the pipeline's `--fixture-environment` with provider `external` and
the explicit `scripts-management-parity` suite. The profile requires its URL and
control-token environment keys before any target is discovered. No scene or
domain is needed. The fixture is a host process, never an Overte replacement.

The private control connection registers an unpredictable session and reads its
append-only observation journal. Its bearer token is removed from every adapter
subprocess environment, including discovery, diagnostics and module calls. It
never occurs in served JavaScript or stdout. Private fixture responses cannot
redirect requests to another origin. Source URLs are not control credentials.
The server freezes its checked-in diagnostic source at startup. Registration
and every observation must carry its actual SHA256 matching the test workspace;
an older or foreign fixture cannot silently stand in for the current test code.

The actual checked-in `fixture/script_management/client.js` uses the ordinary
Script.include API to load its companion. Each real script-engine instance
generates a fresh UUID and sends serialized start/tick observations through its
own XMLHttpRequest. The fixture accepts only ordered events with the served
session/companion proof. Retried HTTP acknowledgments add no activity. Engine
ending cancels its timer and pending request. There is no cooperative "stop"
endpoint that an adapter could use instead of the user's Stop control.

The shared assertions require source and companion delivery plus multiple
received execution events. Restart and load-after-stop need distinct new engine
instances. A bounded sliding window requires at least three real seconds of
silence from every stopped engine while the new engine continues. One request
already in flight may retire; a leaking old engine cannot qualify. The failure
case requires an actual404 request and continued silence, so an ignored load
button cannot pass merely because no new engine appeared.
Quiet durations use the fixture's actual monotonic capture clock. Every active
engine must have recently received events at that capture, so early ticks from
an engine that has since died cannot qualify a restart. Slow native continuity
checks after a snapshot do not extend its observation interval.

Every observer snapshot must be fresh and preserve the exact earlier journal
prefix. Replayed snapshots, rewritten history, process replacement and cleanup
errors fail. Polls, instances, event sequences and host capture intervals are
retained by the existing runner. Fixture control cleanup preserves a primary
test failure if cleanup also fails.

This covers normal URL management and actual execution, not local folder/file
imports, script persistence after application restart, every consent rejection,
or the entire Scripts feature. Source/artifact/installed-code binding and real
platform observations remain required. The HTTP journal is evidence from the
owned diagnostic, not a claim of authenticated arbitrary script execution.

# Joined Phone Script measurements, version 2

`_script_measurements(selector, run, fixture_url, read_only=False)` connects the
existing original APK/PID-start/session-bound sources to `PhoneScriptMeasurements`.
It requires the current original staged-file owner for that run, verifies all
four actual fixture files and obtains the original native directory. It never
stages, loads, stops, restarts, opens/closes a dialog or changes preferences.
`read_only=True` uses the non-repairing existing-session path throughout. The
read-only native allowlist additionally admits only the exact owned fixture
**observe** command; stage/release remain forbidden.

`read(ticket, after_epoch)` independently acquires original execution/code/module/
effect/load history, Phone UI inventory, current Script service rows and native
lifecycle. The ticket and barrier scope the current owned challenge; no expected
state or verb is accepted. The reader rechecks fixture bytes, original bound
continuity and all existing per-source validators. It retains in-process native
instance/cursor/immutable-prefix checks and independently pins the diagnostic
instance and advancing service cursor. Whole acquisition is limited to 20
seconds; existing individual getter and enclosing runner bounds also apply.
Unavailable, ignored, incomplete or inconsistent sources fail with a fixed
private-safe error, preserving file/input ownership.
Original file, execution and lifecycle native instances must additionally agree;
a matching PID/current nonce cannot mix native births. The UI has its separate
original UI-instance identity and is pinned independently.

Version 2 additionally requires the [original all-known manager source](../../native/SCRIPT_MEMBERSHIP.md).
Pending owned managers cannot hide behind an empty public running hash. Every
eligible engine must have its actual matching assigned manager identity/URL;
an additional pending owned manager blocks a clean observation. Version 1 had
one internal live factory, no persisted result format and no full/device-qualified
producer. That factory now emits/requires v2; no v1 full producer is retained.

`compose` is a pure join of those original packets, not a source or input ACK.
It repeats schema, actual PID, native lifecycle and freshness checks. Every
capture must follow the supplied barrier and remain within the existing 1500 ms
age/coherence bound. The returned capture epoch is the **oldest** original
capture, never host UTC or the newest source's timestamp.

The six fields are derived as follows:

| Field | Required original measurement |
| --- | --- |
| `running` | One unique exact staged main URL in both native engines and the independent Script service; actual active/not-stopping/not-finished flags and the submitted UTF-16 hash/units of the independently controlled original main bytes. |
| `companions` | Actual loaded relative module URLs from that actual engine; missing loads remain absent. Unknown/foreign extra modules and cached companion loads cannot become the one allowed alias. |
| `effects` | Actual unique local Box, current owned name/run data/ticks and alternating native color. Missing Box yields zero; missing tick data, wrong heap/type/data/color or orphan effects fail. The common journey separately requires advancing ticks across stable samples. |
| `open`, `picker` | The complete original passive UI inventory and original tablet visibility; input carrier visibility and closing acknowledgments are irrelevant. Outstanding system requests fail this Qt-only recipe. |
| `error` | Current full owned URL and ticket in the actual manager status, equal independently bound visible Label text, plus one original `NotFound` failure callback after the barrier and separate engine/service absence. Unknown errors, stale callbacks, foreign origins/tickets and broken bindings fail. |

Local service `path` deliberately requires the actual decoded absolute path,
without a `file://` scheme. This follows `ScriptEngines::getRunning()`; its `url`
separately retains the full canonical file URL. URI-shaped synthetic service
paths cannot qualify. URL normalization detects disguised ownership but never
converts an encoded, queried or wrong source URL into an eligible main. Foreign
engines may not borrow modules from the owned tree. Unknown actual observations
are not redacted into expected public aliases.

The private result contains exactly `measurementVersion:2`, `state`,
`capturedEpochMs`, `lifecycle`, `engineInstance`, `effect`. Only measured `state`
is eligible for later actor facts, after that actor acquires its own sources.
Native engine/effect metadata and all raw paths/data stay private. Returning a
copy prevents callers from altering the original history/lifecycle.

This is a live internal reader for **existing staged fixtures**, not a complete
feature producer. Before advertising `feature.scripts.*`, the coordinator must
add initial baseline without staged resources, explicit restart handoff for the [durable original-source transcript](SCRIPT_HISTORY.md),
separately frozen load barriers, one-send normal action ownership,
verified restart transition, joining [actual fixture HTTP failure receipts](../../feature_journeys/SCRIPT_HTTP_SOURCE.md), an independent
publisher with separate acquisition and serialization, and complete idempotent
engine/effect/UI/file cleanup. The live component alone is ephemeral; use the durable wrapper across CLI calls.
Neither reader may adopt a requested restart. Pure joins alone do not prove callback cause, actual
HTTP delivery, process death or fixture removal. No capability is promoted here.

The existing mandatory Phone runtime owner registers the device-free
`test_script_measurements.py` group in both modes. All **32** cases pass,
including actual-service format, wrong code, missing results, foreign companions,
orphan effects, stale/foreign errors, broken Label binding, original clocks,
source replacement, ignored acquisition, owner loss and deadline enforcement.
Four additional factory cases use the actual bound wrapper and original
file/readers; all **149** Phone feature-adapter host cases pass. SDK/ADB/native
boundaries remain synthetic. C++ is uncompiled; no device acceptance is claimed.

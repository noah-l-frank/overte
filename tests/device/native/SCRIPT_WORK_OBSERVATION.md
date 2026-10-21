# Original manager-thread Script work, version 1

The E2E-only `Test.featureScriptWork(command)` observes actual Script timers and
running timer/signal callbacks through a queued read on the selected manager's
own thread. It does not evaluate code, create/clear product timers, restore
animation, dispatch input or change a product setting. Native C++ remains
uncompiled; host tests cover Python/JS logic and explicit synthetic boundaries
only. No complete Emote capability or physical qualification is enabled.

## Request and native authority

The exact request is `schemaVersion:1`, `commandId:<32hex>`,
`action:"feature-script-work-observe"`, `managerInstance:<32hex>`. The existing
`ios-<32hex>` read nonce grammar is also accepted by the shared protocol; no iOS
adapter is implemented here. The subject ID must come from an original native
Script observation. It selects a real all-known manager; it is not a requested
result. The actual manager's own membership/code are returned independently.
An unknown, replaced, stopping or unavailable subject is not an empty inventory.
No timer count, callback count, source code, URL or desired state is accepted.

All native code is guarded by `OVERTE_E2E_FEATURE_TESTS` and `--testScript`.
The Test getter additionally requires its existing private results/lifecycle
scope. It marshals to its usual GUI owner, which posts a normal-priority queued
read to the actual manager and returns pending immediately. It never blocks the
GUI waiting for that worker or reads its timer map from a foreign thread.
Already posted normal Qt input deliveries precede the worker read. A full
feature must place this read after its original input/effect barriers; this is
not a claim that every arbitrary future application callback is absent.

The queued worker reads its actual `_timerFunctionMap`, current QTimer
properties and engine evaluation status. E2E scopes around actual V8 signal
callback calls and actual `timerFired` JS execution count active signal/timer
callbacks, including nested event-loop reentry. Invalid callback accounting or
wrong-thread access makes the source unavailable. The worker records its own
actual capture time and completed query data. One outstanding query per subject
is deduplicated; a different query while pending cannot replace its authority.
Dead/stopped owners and failed queue dispatch cannot produce successful zeros.

## Exact original response

The full envelope has `schemaVersion:1`, `requestId`, native feature `instance`,
native `sequence`, `processId`, `requestedEpochMs`, `capturedEpochMs`, `source`.
Requested time is the original native enqueue time. The worker's capture time
is preserved separately; a later GUI read never retimes it. The GUI caches an
exact completed command/result pair and rejects conflicting reuse.

Source has exactly `complete`, `revision`, `manager`, `code`, `work`, `workers`.
Revision is the original all-known-manager registry revision, checked again
after collection. Manager is its actual existing load-membership record:
`instance`, `assigned`, `url`, `loadGeneration`, `assignedEpochMs`. Code is its
actual submitted UTF16 identity. Both originate in the selected worker and
must still match its native current membership/code when the GUI returns.

Workers contains the complete bounded all-known set, at most 128 rows. Each row
has `membership` and actual `running`, `stopping`, `finished`, `done` booleans.
Pending/unassigned managers remain visible. This supports later detection of
other live assignments or retired/reappearing managers; matching filenames and
requested subject IDs cannot stand in for actual membership.

Work has exactly `scriptWorkVersion:1`, `requestId`, manager query `sequence`,
original `requestedEpochMs`, original `capturedEpochMs`, `signalCallbacks`,
`timerCallbacks`, `evaluating`, `timers`. Timers contains at most 256 actual map
entries, ordered by original positive handle, each with `handle`, `active`,
`singleShot`, `intervalMs`, `remainingMs`. Inactive timers still exist as entries.
An inactive timer has remaining time -1; an overdue active timer may report zero.
The inventory does not infer removal from nominal duration or a UI receipt.

## Probe, Phone transport and bounds

The existing private probe dispatches the closed request and saves
`feature-script-work.json`. Pending owner-thread reads are polled with the same
request up to 50 times at 50 ms. Replaced reads cancel their probe timer and old
callbacks cannot publish. Probe shutdown clears its own timer. Missing native
hooks, native errors and an expired pending read save unavailable, never a
successful empty work object. This polling timer belongs to the probe's manager,
not the selected Emote subject.

`NativeScriptWork.read(manager_instance,after_sequence)` sends one new read
nonce, with the existing five-second/51-read bound and 256 KiB JSON limit.
Complete validation requires the actual selected live manager, original code,
complete all-known membership, strictly advancing native and worker counters,
nonregressing native request clocks and separately fresh worker capture.
Both external clock age and a monotonic elapsed-age floor enforce 1.5 seconds,
including final session guards and copy/validation work. Historical `restore`
accepts at most 1,024 original packets and replays the existing membership
retirement checks. It performs no transport and supplies no fresh result.

Phone `_script_work(selector,read_only=True)` requires an existing session and
preserves actual candidate/APK/process/session checks. Its read-only command
admission allows only this exact observation. It cannot repair a session or
accept mutation/expected-state fields. Output remains private; public feature
facts must use their documented aliases rather than raw manager/session IDs.

## Required feature join and cleanup

The complete Emote owner still must join this actual manager/code/assignment to
its original configured-root/source/Rig/widget records, normal input barriers,
independent actor/image effects and original restore observations. It must
account for other live relevant workers and require an actual bounded quiet
window with no owned timers, active callbacks or evaluation. Empty timers alone
do not establish quiescence or feature success. Default script connections and
unrelated application callbacks are not declared globally absent by this source.
The getter owns read-only metadata, not a product input/timer lease, and provides
no successful cleanup operation. Full actual resource release and exact private
owner/evidence retirement remain separate mandatory obligations.

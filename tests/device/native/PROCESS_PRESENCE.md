# Original native process presence, version 1

This passive E2E-only source closes a restart-proof gap: a Stop ACK, a different
current process or an unsuccessful transport read does not establish that the
old process exited. `Test.featureProcessPresence(command)` makes one actual
POSIX `kill(queryProcessId,0)` existence query. Signal zero sends no signal;
the source never stops, starts, activates or changes another process. It
preserves the calling thread's previous `errno` after capturing the actual call
result. Default-off `OVERTE_E2E_FEATURE_TESTS`, explicit `--testScript`, valid
native lifecycle and the original private result directory remain mandatory.

The source is **uncompiled** and **untested on devices**. In particular, an iOS
sandbox or OS policy may refuse this query; that produces `unknown`, never a
successful exit proof. A full adapter must fail when mandatory exit evidence is
unavailable. It must not fall back to a Stop ACK, empty SDK output or guessed
PID replacement. A separately versioned, independently observed OS-service
source would need its own implementation and qualification if this one is
unavailable on a target.

The closed command is exactly `schemaVersion:1`, `commandId:<32hex>`
(`ios-<32hex>` over HTTP/AFC), `action:'feature-process-presence'`, and
`queryProcessId` (an actual previously observed positive PID, at most
2147483647). No signal, process name, selector, path, expected result or code is
accepted. The query PID identifies the object measured, not an expected
measurement. The adapter must obtain it from its original owned source before
restart and retain it in private ownership state.

The original getter packet has exactly:

| Field | Meaning |
| --- | --- |
| `processPresenceVersion` | 1 |
| `commandId` | Exact source request nonce |
| `instance` | Actual current native feature-source birth identity |
| `sequence` | Actual acquisition sequence, 1..1000000000 |
| `processId` | Independently read current application PID |
| `queryProcessId` | PID passed to this actual kernel query |
| `requestedEpochMs`, `capturedEpochMs` | Original native acquisition clocks |
| `presence` | `present`, `absent`, or `unknown` |
| `nativeResult` | Actual syscall return, 0 or -1 |
| `nativeError` | Captured error for failure, canonical zero on success |
| `errorSymbol` | Actual `NONE`, `ESRCH`, `EPERM`, `EACCES`, or `OTHER` classification |

Version 1 pins the Linux/Android and Darwin/iOS errno ABI; the native header
statically requires ESRCH=3, EPERM=1, EACCES=13. `present` requires result 0,
error 0 and NONE. Only result -1/error 3/ESRCH establishes `absent`.
EPERM/1, EACCES/13 and other positive error codes remain `unknown`; a label
cannot change a permission error into absence. The host rejects an application
claiming its own absence. A reused still-present PID is conservatively present;
this source does not identify another process's executable or prove old-birth
exit when that PID has been reused.

The existing JavaScript probe preserves the original packet in the fixed
private atomic 0600 file `feature-process-presence.json`. Repeating its current
command nonce does not repeat the query. An unavailable getter publishes
`available:false`, which is invalid exit evidence. Android reuses its existing
private channel; iOS reuses the closed fixture HTTP/AFC route. The file is a
bounded diagnostic, not a product resource or arbitrary file-read capability.

`NativeProcessPresence` accepts only the original private bytes, actual native
clock and existing candidate/process/foreground guards. It acquires separate
native clocks before and after the query receipt, requires request/capture
freshness, rejects native/monotonic clock regression and includes all I/O and
validation in the existing five-second, 51-read limit. The packet is bounded to
8192 UTF-8 bytes. Foreign request/query/current PID, new source birth, reused
sequence, malformed types, duplicate fields and missing/partial output fail.
No input is replayed. Failed final qualification commits no reader cursor.

`read(pid)` preserves all three measured states. `require_absent(pid)` accepts
only the actual ESRCH receipt. Neither helper establishes candidate continuity,
new process/source identity, actual autoloaded code, effects, file ownership or
successful restart adoption. The full coordinator must separately establish
those facts and retain unresolved ownership if any join fails. Public feature
output must use the existing aliases/privacy rules, not expose private PIDs or
target information. Cleanup never terminates the queried process through this
source; normal separately owned application teardown remains separate.

Eleven host methods use explicitly synthetic native/kernel boundaries and run
the actual Python reader/closed fixture/original JavaScript probe. They cover
ignored/missing/foreign/stale results, self-absence, unknown/permission cases,
relabeled wrong errno, independent clocks/deadlines, cursor retention, command
scope, caller mutation and unavailable hooks. These checks prove test logic
only. Internal `_process_presence` factories now exist on the three separate
local platform branches. Phone/Pico use their original candidate/PID-start/
foreground (and Pico OpenXR) private readers. iOS uses its raw qualified native
scope without a Scripts profile/editor, exact HTTP/AFC documents and separate
native clocks; legacy/unbound entrypoints refuse before target/transport I/O.
Their host selections pass Phone 110, Pico 24 native-feature and iOS 400 no-build
cases. Full restart ownership joins remain pending; no complete feature
capability or device qualification is enabled.

The host reader retains two detached originals before its final ownership guard
and original device-clock read: one for the caller and one for its cursor. The
unchanged five-second query deadline never replaces the stricter 1.5-second
accepted-packet freshness check. Physical result acquisition, parsing,
validation, both copies and final guards share that host elapsed-age bound;
advancing native epoch and final-clock call time are checked independently.
A frozen host/device clock cannot conceal a jump of its other original clock.
A failed final check never commits the new cursor or returns an ESRCH verdict.
The protocol remains v1; neither EPERM/unknown nor a stop acknowledgement is
reclassified as process absence.

Focused synthetic-source countercases cover both final copies, the final guard
and clock, regressing epoch and a slow physical read. The unchanged historical
reader fails the final-guard/clock and physical-read counterprobes; the corrected
original reader passes all 14 process-presence host tests. These checks do not
claim that an Android process or physical device was run.

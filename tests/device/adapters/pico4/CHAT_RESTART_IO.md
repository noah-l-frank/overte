# Original once-only Chat restart IO v1

`PicoChatRestartIO` is a narrow transport for the pending whole Chat application
retirement owner. It executes no input during construction. The private Pico
`_chat_restart_io(target, binding)` factory first verifies the existing original
script/UI binding, candidate and exact target. Construction captures the
original held host session cursor through
[the original binding transfer](../../openxr_input/BINDING_TRANSFER.md).
A real numeric kernel PID:start ABI is required; a synthetic/sample firstSeen or
PID-only value cannot qualify the original process.

`stop(before_input)` admits at most one `adb.shell(target, "am", "force-stop",
"org.overte.pico")` call. It preserves actual live candidate/process/session
checks and the unchanged original held cursor. Its final callback is followed
immediately by that one original SDK call. It neither waits for a desired
process state nor discards a cursor, calls generic cleanup or reports death.
A missing SDK receipt leaves the attempt issued and cannot repeat the command.

`stopped()` uses the existing original bounded `AndroidProcessQuery`, preserving
its actual complete UID/PID-selection packet. Only an empty valid original PID
selection returns stopped. This is not kernel ESRCH, start identity or permission
to adopt another process. Errors/permissions/invalid headers never mean absent.

`launch(before_input)` admits at most one fixed E2E activity start, preserving
the original debug launcher arguments. It separately rechecks old-PID selection,
actual package running/identity state, candidate, activity/arguments and the
original cursor. An original or uninvited new running process prevents launch;
there is no hidden repair force-stop or second launch. The final callback is
followed immediately by the one fixed `am start -W -n` SDK call. It does not call
`launch_debug_app`, a generic app facade or OpenXR cleanup. Lost input receipts
are never replayed. The surrounding `RestartInputs` must durably own each actual
attempt before these callbacks and retain every unknown original journal.

Both SDK commands return only `requested:true`; this is deliberately not an
absence/launch/resource verdict. The whole owner must use actual new sources.
Their final callbacks may qualify independent HTTP/OS/native sources because
they do not run inside a controller-session lock. They must retain the original
parent/child CAS age and exact original cleanup admission before the real input.

`unbound_sources()` obtains the original raw controlled-debug identity BEFORE
any old host cursor is replaced. It requires a different PID and greater actual
start value, unchanged candidate and foreground controlled package. It returns
new original `NativeFeatureObservation`, `NativeProcessPresence` and
`NativeChatProfileCurrent` readers using the existing native writer/private
result files. Their guards use the actual raw debug/process source and candidate,
not an old host session binding. Only the three closed read-only source commands
are allowed. Cache creation, profile acquire/restore, arbitrary control input
and caller expected values cannot enter this transport. It never binds the new
process from an ACK. The enclosing owner must join actual old-PID ESRCH, distinct
native birth/launch counters, retained original profile fingerprints and source
freshness before the separate host cursor replacement API is used.

`close_host()` closes only the original held host handles. Old context files,
input journals, unknown prepared files and the original OpenXR cursor remain
retained unless separately and explicitly replaced by the qualified binding
transfer. Default Graphics/lifecycle/app-launch behavior is unchanged.

Focused checks use actual private session files/OFDs and the original transport,
source readers and Pico factory logic. Android SDK/kernel/native responses are
explicit producer seams. They prove exact one-command attempts, lost stop/launch
receipts, no hidden repair/session deletion, real closed source validation,
current source acquisition with the old cursor still held, candidate changes,
expired admission, live/uninvited process refusal and no mutating source command.
The original Pico factory tests qualify actual verifier/binding integration with
synthetic installed/device IO. No actual app/device/ADB/OpenXR command is run.

This component alone does not run the process retirement/recovery journey,
compare old/new native births or profiles, close final peer IPC, archive original
scopes or complete Chat. Those actual joins are pending whole-parent work. No
public Chat capability or hermetic peer build receipt is added.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device:android/vr/pico/tests/device python3 -m unittest self_tests.test_pico_chat_restart_io test_chat_restart_io -v
```

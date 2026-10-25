# Pico Script restart host binding, version 1

The internal `_script_restart_source` can recover a missing original host
OpenXR nonce journal after a previously issued normal launch lost its receipt.
It is not a second launch route. The current delivery call still fails; only a
subsequent reconstruction may enter this observation-only recovery. No Android
launch/activate/stop, OpenXR grant submission, controller command, Script input,
file restaging or UI input occurs here. It never overwrites a present binding.

Prerequisites are the exact private `RestartInputs` record at `launch-issued`,
a full original prepared Script handoff identical to the frozen snapshot, and
actual absence of the original host session file. `is_unbound()` is locked and
read-only: invalid state, links (including dangling links), wrong permissions
or a corrupt journal do not mean absence. A present ordinary binding continues
through every existing normal source/session guard; a foreign one is rejected.

Before any unbound control-probe query, compare current actual installed bytes
and source against the independently selected frozen candidate, plus the exact
original target/configuration fingerprint. The original raw debug-probe/OS
identity getter must report a genuinely different positive PID/start identity.
It grants no input authority. Use this original identity only to acquire the
existing guarded native observation and old-PID kernel-presence sources through
the same fixed private paths and command allowlist.

Require a fresh original native birth and persisted lifecycle counters satisfying
exactly the shared restart comparison. Require actual `ESRCH` for the original
old PID from this same new native instance; absent SDK/pidof output and a changed
PID are insufficient. Acquire a second advancing native sample in that same
instance, with capture time at or after the exit observation, and repeat the
counter comparison. Every read checks the current installed candidate, selected
target, original raw probe/OS identity and monotonic deadline. Unavailable,
foreign/stale, permission/unknown exit, original birth, missing/extra launch,
changed source or replaced process rejects recovery with all owners retained.

Recheck unchanged input intent and the full prepared handoff plus actual host
binding absence before the original atomic, locked `session.begin(identity)`.
This writes only the private host nonce/sequence journal; it submits no device
grant. Recheck the original process/source guard and ordinary session identity.
The complete recovery has a 30-second monotonic bound including owner/preflight
reads and host writes, with checks before new queries and binding. Native source
acquisitions retain their existing five-second bounds. No timeout is widened.
A late/uncertain host write retains ownership for independently checked recovery.

Afterward the original `_script_runtime`, installed candidate, OpenXR session,
`RestartInputs.observe` and full Script handoff execute again. Only those later
original checks can establish a new qualified binding, unchanged staged bytes,
actual empty execution/UI and three seconds of absence. This helper supplies
none of those feature verdicts. An ignored original launch still fails, and no
issued stop or launch is repeated. General cleanup continues to reject unresolved
input/file/manager/handoff owners; the new host nonce is handled only by the
existing normal session cleanup. No complete feature triple is registered.

Host checks use explicit synthetic SDK/OS/probe/native boundaries and real
private ownership/nonce files. They test lost launch receipt recovery without
replay, unknown exit, old birth/unchanged counters, current candidate ordering,
foreign host bindings, expired recovery and invalid/dangling host state. They
prove adapter logic only. Native C++ is uncompiled, latency is unqualified and
Pico hardware remains untested.

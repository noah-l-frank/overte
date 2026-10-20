# Phone Authentication original-source acquisitions v1

`overte_phone_authentication.PhoneAuthenticationSamples` is an internal source
owner, not the complete `feature.authentication` adapter. Script is still the
only complete Phone feature extension. Native instrumentation remains
uncompiled, and all physical-device acceptance remains pending.

## Admission and acquisition

The caller must hold the existing `phone-script-sources.lock` for the entire
acquisition: Authentication uses the same fixed native command channel as
Script. The caller supplies an attached existing HTTPS account-provider v2 run,
its original provider instance, the primary or independent actor role, explicit
process stage 0..3, and a native-clock input barrier. The source owner never
registers/activates a run, requests desired state, changes the account endpoint,
logs in, opens UI, repairs the SDK session or restarts a process.

Every acquisition persists pending intent before opening a source. Under the
existing candidate/session pin it reads the actual native Test birth and
AccountManager state, requires the controlled HTTPS endpoint and an anonymous
or run-owned cached principal, and stages one exclusive observer-origin lease.
This lease authorizes only the native protected measurement request; it does
not set product account state. The debug-launch environment must have selected
the same actual endpoint before startup; see [launch scoping](ACCOUNT_FIXTURE_LAUNCH.md).

The owner independently acquires original Login UI v2, passive tablet inventory,
and a nonce-bound protected HTTP GET sent by the actual AccountManager transport.
Its token, principal hash, credential generation and AccountManager instance
must agree with fresh native state both before and after that GET. Native Test,
AccountManager and the two UI source births are distinct; none substitutes for
another. Only the actor requests the provider's matching original HTTP fact.
Primary input credentials and the actor publisher credential remain separate.

The owner then releases its protected request and inspects actual zero inflight
requests/body/credential bytes. It releases the observer origin and independently
observes both files absent and the original ownership retired. Finally it reads
the provider's typed delayed-grant history and actual authority counts.
Remote issued authority is a resource even when no local client adopted it.

## Persistence, errors and cleanup

Private primary/actor journals and probe owners are separate. Each journal
records the original envelopes and accepted source cursors for one process
stage. Recreating the owner validates the saved envelopes and cursor
correspondence before sending anything; it never returns a cached success.
Fresh native/UI cursors cannot hide a changed birth, rewritten account or
delayed-grant history, regressed clock, or forgotten source prefix.

The whole acquisition is bounded to 20 seconds, including fixture creation,
source requests, host HTTP joins, cleanup and journal persistence. Existing
per-source bounds remain active inside that budget. Native and provider clock
domains remain separate. The oldest contributing native clock must be after
the actual input barrier and within 1.5 seconds of the other native captures;
original provider clocks must independently be fresh.

An ignored/missing/foreign/stale source, retained measurement bytes/files,
candidate loss, storage failure or uncertain result leaves pending provenance
and original sublease ownership. Neither recreation nor a repeated read may
reset that pending acquisition. The future full coordinator must drain these
owned leases while preserving uncertainty, fail the run, and retire host
journals only after independently observed run cleanup. A successful input ACK
never satisfies this source protocol. No full capability is advertised here.

The read-only command pipe admits exact native getters, protected measurement
read/release/inspect, origin observe and Login UI observe. It rejects origin
stage/release, UI input and all desired/credential/URL fields. Measurement-origin
staging uses the ordinary fixture owner only inside the existing session pin.

## Device-free verification

`android/phone/tests/device/test_authentication_samples.py` exercises the real
source readers, real private journal/fixture files and explicit synthetic native
and provider seams. Twenty cases cover role separation, actual 200/401 joins,
pending/error UI, foreign account/endpoint, ignored source input, retained files
and credential bytes, lost writes, stale owners, source reconstruction, delayed
authority, wrong proofs and acquisition deadlines. The existing Phone adapter
tests also verify the concrete read-only factories and both-role cleanup.
These simulations establish test logic only; they do not execute an APK.

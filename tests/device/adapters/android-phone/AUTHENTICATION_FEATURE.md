# Android Phone Authentication feature v1, shared contract v16

The existing Phone Appium entrypoint implements
`feature.authentication.act/observe/cleanup`. Normal inputs, causal native
readiness, separate primary/actor sources, three explicit restarts, fixture
authority and verified cleanup are composed in the existing journey system.
The full common seventeen-step journey passes through that entrypoint in host
tests. These simulations verify control logic only. Native instrumentation is
uncompiled; no APK, device, installation, build or Jenkins run was executed.

## Required configuration

Enable `OVERTE_PHONE_FEATURE_AUTHENTICATION=1` and
`OVERTE_PHONE_ACCOUNT_FIXTURE=1`. Supply the existing
`OVERTE_E2E_FEATURE_FIXTURE_URL` as an exact controlled HTTPS
`/feature-fixture/v1` URL and `OVERTE_E2E_FEATURE_READER_TOKEN` privately. The
target must be the verified Phone debug candidate, with `android-debug-e2e`
launch and `appium:autoLaunch: false`. The account fixture must be trusted by
the actual client and supply original provider v2/TLS readiness. There is no
TLS bypass or trust-store installation in this implementation.

The debug launcher sets only this process's `HIFI_METAVERSE_URL` before native
AccountManager startup; it does not change stored endpoint preferences. Repeat
that exact configuration on each explicit restart. Actual native endpoint
hashes must agree; a warm process using another endpoint fails. Instrumentation
must be present in the actual debug build; an absent getter cannot turn green
through the environment flag. See [launch scoping](ACCOUNT_FIXTURE_LAUNCH.md).

## Ordinary input and fresh evidence

The closed v16 verbs use the existing Login controls and guarded File-menu
logout. Private fixture credentials go directly to ordinary fields and never
enter public arguments, records or diagnostics. Every input persists original
scope and pre-input intent. An uncertain normal input is not replayed. A
durably delivered input may reacquire original readiness only. Completed
duplicate tickets revalidate scope without input.

Input ACKs are insufficient. Submit needs a new original native reply after
the actual Submit barrier and actual cached-profile readiness. Delayed submit
requires the original provider's held request for that ticket plus real native
pending state. Cancel/reopen preserves that native request. Logout needs its
new original native signal, advanced credential generation, empty principal and
absent access/refresh/pending state. Fixture activation already owns stale-grant
release and cleanup revocation; the adapter never repeats these mutations.

Every observation independently obtains current native account/lifecycle,
original Login UI, passive tablet inventory, a nonce-bound HTTP request through
the actual current AccountManager transport, original delayed-grant history and
actual remote authority counts. The actor additionally retrieves its matching
original server fact using its separate credential. Native Test, AccountManager
and UI births are distinct identities. Fresh native responses must match the
account endpoint/generation/token state; no requested state is a getter input.
The oldest contributing actual native clock supplies the public capture time.

Each sample releases its temporary protected request and independently inspects
zero inflight/body/credential bytes. It releases the observer-origin lease and
observes actual file absence/retirement. Unreleased leases are not hidden from
resource inventories or general cleanup. Same-ticket failures retain pending
provenance. The same live actor may retire only an actually changed-ticket
acquisition under its still-held lock, preserving accepted cursors and sending
no product input; old data is never relabelled or published for the next phase.

## Restarts and independent publisher

Stop/launch use the existing one-send `RestartInputs` protocol. A lost return
resumes its original phase without redelivery. Actual OS stopped state, a new
PID/native Test/AccountManager birth, unchanged candidate/SDK/target and original
kernel ESRCH are mandatory. Every role needs its own old-process frame and its
own new kernel observation; primary history cannot supply missing actor facts.
Stage 0..3 source archives and global role sequences do not reset or mix.

Use the existing `script_observer.py --config <private-config>` entrypoint for
both supported areas. Authentication uses this exact v2 configuration:

```json
{
  "featureObserverVersion": 2,
  "area": "authentication",
  "target": "<private configured selector>",
  "candidateArguments": ["<complete existing verified candidate arguments>"],
  "fixtureUrl": "https://<trusted owned fixture>/feature-fixture/v1",
  "actorToken": "<separate private actor credential>",
  "durationSeconds": 1800
}
```

The configuration is an owned 0600 regular file in a canonical 0700 parent,
without symlinks/shared links. All existing candidate identity arguments are
verified before target use. An inherited reader token is rejected. The worker
disables its primary feature advertisements, never calls primary observe or
repairs/creates an SDK session, and has no ordinary input path. Its own temporary
measurement fixtures are still staged/released through their guarded owners.
Only genuine source-lock contention and pending phases are retried. Original
retired-account/zero-authority status or a verified host-retirement plan ends
the worker. Legacy Script `scriptObserverVersion: 1` remains supported.

## Time limits and cleanup

The existing per-source and HTTP limits remain active. A complete acquisition
is bounded to 20 seconds, normal input to 30 seconds, causal readiness to
20 seconds, cleanup to 30 seconds and final journal retirement to 30 seconds.
The worker duration is 30..1800 seconds. The product's native token deadline is
still 15 seconds; pending view steps must fit within it. No instrumentation
extends that timer or treats a timed-out request as still pending.

Cleanup first journals cleaning intent and tries normal owned view dismissal,
logout and tablet close, including native observations when a main source read
was interrupted. It separately drains both role probes and the original
observer origin. It then requires fresh anonymous/UI-closed/HTTP401/zero-authority
frames for three seconds in both monotonic and native clocks. A second cleanup
acquires fresh originals without replaying prior input. A stuck input, changed
scope, ignored close, frozen clock or interrupted source ledger fails and retains
provenance; SDK teardown is still attempted by general cleanup.

Finalization requires both roles' own cleanup frames, every process-stage
archive, the original account fixture retired and zero remote authority. It
queries new native/UI absence and both original retired origin tokens. The
native probe has one global current slot: finalization inspects its latest
actual request, while both roles' original frames separately prove their own
earlier releases. An older replaced request cannot be queried as if it were a
retired-request registry. It sends no new protected HTTP GET after fixture retirement. A bounded
manifest hashes only the known private owner/source/input/restart filenames;
each interrupted retry rechecks native absence before continuing. Changed or
foreign records are never deleted. The owner is retired last; the SDK's normal
teardown still runs if finalization fails. Missing any required capability or
proof cannot produce a green complete suite.

The lower-level contracts and counterexamples are documented in
[source acquisitions v2](AUTHENTICATION_SOURCES.md),
[normal inputs/causality v1](AUTHENTICATION_INPUTS.md) and
[owner history v1](AUTHENTICATION_COORDINATOR.md). Physical device qualification
must later bind the actual built/installed candidate and independently produced
evidence to its tested version through the Proxmox laboratory.

The closing host selection passes 433 Phone/Authentication/identity/native-source
cases, including 105 focused Authentication cases. The unchanged Script facade
passes 25 cases, and the common no-build selection passes 1,026 cases with no
failures/errors/skips or compiler attempts. Exactly three native compiler-based
voice cases are explicitly outside that no-build selection. These counts do not
represent physical feature acceptance.

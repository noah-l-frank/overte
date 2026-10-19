# Controlled HTTPS account protocol, version 1

The existing feature fixture server now optionally supplies the actual native
password/refresh OAuth and protected profile protocol. This replaces no product
code and changes no client credential/TLS protection. It is a **backend fixture,
not a complete Authentication adapter, native observation hook or independent
actor implementation**. No Overte client/device has used or qualified it.

The reviewed native sources are `libraries/networking/src/AccountManager.cpp`,
`OAuthTokenValidation.h`, `OAuthAccessToken.cpp` and `DataServerAccountInfo.cpp`.
Ordinary password login posts grant_type=password, username, password and
scope=owner to `/oauth/token`; refresh instead has grant_type=refresh_token,
refresh_token and scope. The response has actual random access_token,
token_type=Bearer, expires_in=3600 and refresh_token. The protected
`GET /api/v1/user/profile` reads the actual Bearer token and returns
`{status:"success",data:{user:{username:...}}}` only for valid owned authority.
Invalid credentials, expiry, unknown/revoked tokens and different run ownership
are rejected. The fixture implements only these closed native password/profile
paths, not social login, signup, directory or the remaining metaverse APIs.

## Configuration and roles

Use the existing `feature_journeys/server.py --private-config <owned-file>`
entry point. Its existing readerToken/actorToken/host/port configuration has
optional tls:{certificateFile,privateKeyFile} and accountProvider:true. The
configuration must be an original 0600 file in a canonical private 0700 directory.
TLS material must be original regular absolute files, without symbolic/hard
links; the private key must be owned by the current account with no group/other
permissions. Encrypted keys fail instead of opening a password prompt.

The provider requires an actual TLS 1.2+ server context. There is no plaintext
credential route, insecure mode, certificate-verification override or automatic
trust-store installation. The configured certificate chain/hostname must already
be trusted by the actual native client under its existing policy. A Python host
readiness check proves no native trust. The native metaverse URL must be the
owned **HTTPS origin**, not the `/feature-fixture/v1` resource path, and must be
established through the existing controlled client configuration/input route.
No test may redirect an existing real account or send its credentials to this
fixture. Missing native origin/trust/source binding keeps the adapter unavailable.

The existing private roles remain separate. Reader owns registration, private
test credential delivery and fixture controls. Actor can read original profile
proofs/status and publish independently measured journal facts, but cannot read
passwords or mutate authority. Reader cannot read account proof or publish actor
facts. No control accepts desired principal, protectedAccess, assertions or facts.
Private role tokens and account credentials are distinct namespaces. Source
collisions fail without overwriting an existing token/run. One provider has only
one server owner; closed/retired contexts cannot be reattached or reprovisioned.

`GET /feature-fixture/v1/account-provider` requires a private role and returns
providerVersion 1, actual instance, transport https, actual negotiated tlsVersion
and internalErrors. Authentication registration fails before creating a run if
this mandatory service is unavailable; other feature fixture routes retain their
existing behavior. `Client.register('authentication')` requires HTTPS/readiness
before registration. The actual account username is e2e-<runId>, with a random
private password. Credentials are fixture inputs, never measured login results.

For an authentication run, the reader may GET
`/runs/<run>/account/credentials/<owned|invalid|delayed>` below the existing prefix.
It returns only username/password over HTTPS. Invalid uses a genuinely wrong
password. Delayed uses the same valid owned account, with actual response delivery
held separately. Values must remain in private input transport and never enter
public operation arguments, logs, reports, artifacts or commits.

## Delayed responses, original proof and cleanup

Reader POST `/runs/<run>/account/control` has exactly {operation}, with operation
hold-next, release-delayed or cleanup. Hold-next must be separately observed
armed before ordinary native login input. It holds the next **real matching**
grant request, not a simulated acknowledgement; no token is issued while held.
Release requires an actually waiting grant. Its maximum hold is 12 seconds,
below the native manager's unchanged 15-second reply deadline; release early
enough for the actual network budget. Expiry returns 503, never a valid token or
a successful stale-response case. Cleanup deactivates authority, clears retained
credentials/tokens and wakes pending handlers without late valid issuance.

The independent proof is **not** a token/grant receipt. A fresh native protected
profile probe must use the actual current AccountManager credentials and add
X-Overte-E2E-Run, X-Overte-E2E-Ticket and X-Overte-E2E-Request headers. Run/ticket
are the actual owned 32-hex challenges; request is a fresh 32-hex or ios-32-hex
native request identity. Native origin/PID/candidate/session and original HTTP
response observations must be independently guarded. Arbitrary desired state or
an adapter-side HTTP call cannot replace that native probe.

Only an actually received matching profile request yields an actor-readable
`GET /runs/<run>/account/proof/<ticket>/<request>` event. It retains original
providerVersion, instance, eventSequence, capturedEpochMs, kind=profile-request,
runId, ticket, requestId, actual status, principal owned|anonymous and measured
protectedAccess. The actual Bearer lookup determines those last fields. Requests
with a retired ticket, reused nonce or foreign run token cannot yield this run's
owned proof. Reading an old event preserves its original time; it does not make
it fresh. Native and server epochs must not be equated on iOS; bind by fresh
native request/challenge, actual response and bounded transport. In particular,
grant-issued says nothing about native adoption or UI success.

Pending **client login** cannot be inferred from heldRequests. The independent
actor still needs a separate fresh native pending/error/principal observation,
actual ordinary dialog input/lifetime and native persistence/restart effects.
No publisher currently composes these into the complete common Authentication
contract; no platform advertises its three full feature operations.

GET `/runs/<run>/account/status` separately reads providerVersion, instance,
runId, original capturedEpochMs, eventSequence, accountExists, heldRequests,
armedHold, inflightRequests, accessTokens and refreshTokens. Counts include all
retained owned tokens, including expired entries. Actual grant/profile handlers
remain counted through their response write. A cleanup ACK or empty token map
cannot hide an undrained handler. `Client.close` sends cleanup once, then requires
fresh same-instance empty authority/hold/token/handler observations before
deleting the run. The total five-second cleanup budget includes mutation, reads
and final deletion. Failure retains the client ownership scope. Known retired
scopes permit recovery after a lost final proof; unknown/foreign scopes cannot
be treated as empty. Fixture cleanup proves no native logout or app-file cleanup.

Limits are 32 live account rows, 256 retained retired run IDs, 64 token pairs per
run, 4096 used profile nonces and 1024 original sanitized events per run, plus 16
inflight requests per run. No passwords, tokens, bodies or personal data appear
in proof/status/journal/log output. TLS handshake/IO is bounded; form bodies have
one absolute two-second monotonic deadline and a 4096-byte limit, with duplicate,
malformed, unsupported and expected-result fields rejected before issuance.

## Device-free validation and remaining work

The existing quick control-plane selection registers `test_account_provider.py`.
Twenty-three cases exercise the real loopback HTTPS handler with actual
password/Bearer/refresh requests, expiry, foreign scope, delayed delivery,
authority/handler cleanup, false ACKs, nonce/history reuse, role separation,
credential collisions, trust/hostname rejection and bounded slow-body clocks.
OpenSSL CLI (`openssl`, with -addext support) generates temporary certificate/key
files in a private temporary directory. Only the Python test client explicitly
trusts that certificate; no native client or system trust store is changed.
The fixture service itself uses standard-library TLS with prepared material and
does not generate certificates at runtime. Missing host crypto tooling fails
the required self-test rather than skipping it or installing anything.

These checks prove provider/transport/test logic, not native client login. The
native protected-profile probe, source-bound normal login controls, persistent
ownership, independent pending/error join, actual trusted-device origin setup
and full per-platform Authentication coordinators remain missing. Keep those
capabilities closed and device qualification unperformed until separately met.

# Native protected-account probe, version 1

This is an internal E2E source, not ordinary login input, a complete area adapter
or device evidence. Native C++ is uncompiled. The default-off feature build flag,
explicit testScript/results launch and healthy private native lifecycle source
are mandatory. Standard product OAuth/TLS/request cancellation remain unchanged.

## Private origin prerequisite

Provision `feature-account-origin.v1.json` in the actual isolated native test
results root **before** requesting a probe. Its exact object is
`{schemaVersion:1,runId:<32hex>,origin:<owned-https-origin>}`. Bytes must be sorted
compact canonical JSON followed by one newline. The root must be canonical,
owned 0700; the original file must be owned 0600, regular, single-link and at
most 4096 bytes. Native openat/O_NOFOLLOW checks original inode/path/ownership
before and after reading. Duplicate/ambiguous JSON, symlinks, hardlinks and
unsupported filesystems fail. Only reviewed Unix ownership semantics are
implemented; there is no permissive fallback.

The origin is at most 1024 characters, a canonical ASCII-encoded HTTPS origin
with a host and no credentials, path (including `/`), query or fragment. It must
match the **actual current** AccountManager auth URL, allowing that native URL's
single root slash. This file configures only the observer; it never changes the
product auth endpoint. Prepare that endpoint through the ordinary controlled
product configuration route. No automatic provisioning, endpoint rewrite, CA
installation, insecure TLS mode or live account adoption exists here. Actual
native trust and per-platform origin-file provisioning/cleanup remain required.

The source sends authority only when the actual cached principal equals the
fixture's owned `e2e-<runId>` username. A nonempty token without that original
profile, or any other principal, refuses the probe. Anonymous reads require no
cached principal/token. An owned expired token may yield an actual anonymous
request, because the existing pure authorization-header helper emits no header
for invalid/expired authority. Header bytes are capped at 512. No token, password,
username, response body or endpoint is exported or written into the probe result.

## Closed operation and original response

The existing private Android command channel or existing iOS fixture HTTP/AFC
channel accepts exactly schemaVersion=1, commandId, action=feature-account-probe,
operation=read|release|inspect, requestId, runId and ticket. Both request and
command IDs are 32-hex on Android and ios-32hex on iOS. For read, commandId equals
requestId. Cleanup commands have new distinct IDs and the original requestId.
There is no URL, credential, expected state or assertion field.

Read starts one real native `GET /api/v1/user/profile` with the actual current
cached Authorization header and X-Overte-E2E-Run/Ticket/Request headers. It uses
the original HTTPS credential transport, manual redirects and standard native
certificate/hostname verification. It does not invoke isLoggedIn, refresh,
requestProfile, token setters, normal login or cache/file updates. It observes
remote authority only; UI/login/persistence still need their own ordinary flow.

The existing native credential ticket is watched without changing it. Original
endpoint, cached principal, authorization bytes, token presence and credential
ticket must remain equal at completion. Context replacement, logout/new login,
changed authority, TLS/network failure, redirect, missing/foreign/malformed body
or deadline exhaustion produces no valid result. HTTP 200 requires an actual
success/user body for the owned principal; HTTP 401 requires the actual
fail/unauthorized body. The body is bounded to 4096 bytes. Native QElapsedTimer
and an absolute two-second reply timer cover dispatch, response and actual reply
object destruction. The asynchronous callback retains no expected state.

Polling the same command returns only pending until the original reply has
actually been destroyed, then the immutable original result. It never issues a
second GET or retimes completed data. The JavaScript producer polls every 50 ms,
at most 50 times, saves no pending packet, cancels superseded timers and preserves
native metadata. Missing/late completion remains unavailable. A durable host
ownership intent must precede the one command dispatch; file retries never
redispatch that GET. IDs are never reused within the native process.

The result has probeVersion=1, commandId, requestId, runId, ticket, operation,
instance (actual AccountManager instance), sequence, processId, requestedEpochMs,
capturedEpochMs and source. Read source has actual httpStatus, Qt networkError,
parsed, principalSha256, responseSha256, responseBytes, tokenAttached,
credentialGeneration, endpointSha256, sentEpochMs and completedEpochMs. Hashes
cover original UTF-8 profile identity, original response bytes and actual encoded
native auth URL. HTTP 200 requires no network error and an actually attached
token. A 401 has the empty-principal hash; that does not erase an owned cached
native profile or prove native logout. No result is synthesized from the supplied
run/ticket, desired login state, grant ACK or UI input.

## Independent joins and cleanup

The typed reader requires the original process, current unique request/run/ticket,
strict advancing cursor/context and ordered native times. Acquisition has one
five-second/51-read monotonic budget and the existing 262144-byte JSON bound.
iOS compares original native epochs only; unique correlation and bounded local
transport handle device/host wall-clock skew.

`bind_to_account` requires a separately acquired later passive native account
sample, matching AccountManager context, actual credential generation, endpoint
hash and actual attached-token validity. It cannot infer UI/error state from a
profile response. `protected_proof` joins an **actor-owned independent native
acquisition** with the controlled HTTPS provider's original profile-request
proof, checking pinned provider context, current nonce/run/ticket, actual status,
principal identity and protectedAccess. Native/provider clocks are separate.
A primary result must not be copied to the actor or published as secondary facts;
reader/actor tokens remain isolated. The helpers are building blocks, not an
implemented journal publisher or a complete Authentication coordinator.

Release retires the exact request and aborts a live reply once, clearing retained
private body/authority copies and invalidating its result. Releasing a never-
delivered intent can retire that unused nonce before a late command arrives;
it cannot displace a different active native request. A release ACK proves no
cleanup. A separate fresh inspect must observe released=true, inflight=false,
responseBytes=0 and credentialBytes=0. Inflight includes the original reply
object through actual destruction, not only its finished signal. Unknown/foreign
scope or reused nonce cannot count as empty. At most 4096 native IDs are retained;
new reads reserve 64 slots for bounded release/inspect cleanup.

`AccountProbeOwner` uses the existing private source/artifact/process/session/
generation binding and one persisted original intent. A second acquisition or
binding change fails. `OwnedAccountProbe` discards that intent only after actual
native drain/absence; failure retains it for the existing adapter-wide cleanup.
The native origin configuration remains a separately owned prerequisite and
must be removed with original-file ownership/absence verification by its future
provisioner. Probe result metadata is retained private run evidence, not a token
or owned product resource. The actual backend account must still be revoked and
retired through the existing provider cleanup.

## Local checks and open work

Eighteen hardware-free source/reader/ownership counterexamples exercise ignored
commands, old/foreign documents, missing results, failed parsing, status/token/
principal contradictions, rewritten context, provider mismatch, real private
owner retention, no-op/partial cleanup, clock/budget failures and the actual
JavaScript dispatch/poll limits. The HTTPS provider suite additionally joins an
original real server proof with an explicitly synthetic native boundary across
different clocks. These checks do not run native code, send client traffic or
prove product login. Native configuration provisioning, normal login/cancel,
restart ownership, UI error/dialog measurements, independent actor composition
and complete platform Authentication adapters remain open; capabilities stay
closed and all physical qualification remains absent.

# Passive native account observation, version 1

This default-off `OVERTE_E2E_FEATURE_TESTS` source supplies actual AccountManager
flags and original terminal reply/signal history. It is not a complete
Authentication adapter, UI result, protected-access probe or independent actor.
Native C++ is uncompiled; no native/client/device acceptance is implied.

## Source and transport

The existing `feature-native-observe` sampler and private original JSON transport
are retained. `account` still has loggedIn and principalSha256, plus optional
`observation`. New consumers use `read(..., require_account=True)` and reject old
narrow sources. Once a reader has seen this source, losing it is a failure even
without repeating that option. All existing candidate/PID/session/foreground,
nonce, five-second/51-read, size, result and privacy guards still apply.

The sampler invokes `AccountManager::featureAccountObservation()` on the owning
thread. It never invokes isLoggedIn or hasValidAccessToken: those ordinary
product helpers may start a token refresh. It reads the actual cached token's
pure syntax/type/expiry check and actual endpoint presence instead. Reads cannot
log in, refresh, log out, fetch a profile, update account files or emit UI signals.
`loggedIn` retains the cached valid-token/endpoint meaning; it does not assert a
fresh profile or remote authority. principalSha256 hashes the actual cached
username UTF-8 bytes, including the empty value. A token grant can precede a
profile, and an old cached principal cannot establish current protected access.

The observation has exactly accountVersion=1, instance (per-AccountManager
32-hex context), capturedEpochMs, credentialGeneration, credentialActive,
endpointPresent, endpointSha256, loginPending, refreshPending, tokenPresent,
tokenValid, refreshPresent, transportRejected, eventSequence, droppedEvents and
events. endpointSha256 hashes the actual encoded auth URL, not a proposed
configuration or requested destination. No URL, username, token, refresh token,
password, network error string or response body is exposed.

credentialGeneration comes from the existing RequestScope's actual native ticket
generation, not observation counts. credentialActive reads its actual current
active bit. These diagnostics do not authorize a request, activate a ticket or
change invalidation behavior. Exhausted/unsafe generations and clock failures
make this source unavailable. loginPending/refreshPending read the actual manager
booleans; neither is inferred from fixture heldRequests. transportRejected is the
manager's **last password/provider-login reply** flag and can remain historical;
it must not be relabelled as a new request outcome.

## Original bounded history

The source retains 64 original records with sequence, capturedEpochMs, kind,
credentialGeneration, hasReply, httpStatus, networkError, transportRejected and
timedOut. Explicit droppedEvents accounts for older records. Native epoch values
and surviving records are immutable. A new acquisition does not retime history.

Kinds login-reply, refresh-reply and profile-reply observe actual replies after
the original credential/profile current-request guards and before parsing or
adopting their body. They copy the actual HTTP status, Qt network error code and
original transport-rejected/deadline properties without reading reply bytes.
Stale rejected callbacks cannot be reclassified as current replies. Consequently
some cancellation/timeout callbacks rejected by the original request guard have
no current terminal event; absence is not success or a synthetic failure result.

Kinds login-complete, login-failed, logout-complete, profile-changed and
auth-endpoint-changed record actual native signal delivery on the account owner
thread, before reentrant product signal consumers. Signal records have hasReply
false, zero status/error and false reply flags. A signal is not an HTTP reply,
UI control delivery, password-specific error classification or protected-access
proof. No input cause is guessed from a notification.

The strict reader pins context, native credential generation, source time and
history/drop counters; retained records cannot change. It checks complete ring
sequence continuity, original event times/generations, actual Boolean types and
cached-token consistency. `reply_after` selects exactly one original terminal
record after a native epoch/event barrier in the specified actual credential
generation. Missing, ambiguous, stale or foreign records fail. HTTP 200 alone
proves neither successful body parsing nor profile adoption nor UI success.

For iOS, preserve the original native clock: the correlated request and bounded
host monotonic transport establish acquisition. Compare action barriers with
native epochs from actual source delivery, never a host wall clock. Product
restart requires a new bound reader/source identity; preserved host history
cannot make a different AccountManager look unchanged.

## Cleanup and remaining joins

This source allocates no account, token, app file, panel or held input. It keeps
bounded diagnostic metadata for the native object lifetime and follows the
existing private observation-artifact lifecycle. Retaining history never counts
as retained product authority or as failed logout by itself. The complete area
must separately use ordinary logout and independently observe cleared actual
native credentials/profile, backend revocation, owned dialogs/inputs and files.

The HTTPS [account backend](../feature_journeys/ACCOUNT_PROVIDER.md) exists.
Native trusted-origin/current-credential protected requests, source-bound normal
login/cancel controls, restart/persistent ownership and independently joined UI/
pending/error/remote observations remain required. No full feature triple is
enabled. Twelve device-free cases cover ignored/missing effects, stale/foreign/
rewritten history, typed contradictions, dropped records and receipt-versus-
profile separation; a source guard also checks passive API use. They do not
execute or qualify native AccountManager code.

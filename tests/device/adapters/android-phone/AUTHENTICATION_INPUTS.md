# Phone Authentication normal inputs and causality v1

`PhoneAuthenticationActions` joins the existing Token Login UI v2, ordinary
Phone File-menu logout, existing-session input admission and `RestartInputs`.
`overte_phone_authentication_causality` validates original AccountManager events.
These internal components are composed by the [complete Authentication adapter](AUTHENTICATION_FEATURE.md).
Native instrumentation is uncompiled and devices are untested.

## Inputs and ordinary routes

The owner attaches to the caller's existing controlled HTTPS run and verifies
its exact URL, run, native process, candidate, SDK session and account endpoint.
Preparation reads originals and reserves private host ownership; it stages no
fixtures and sends no functional input. The full coordinator must share this
owner's exact held `phone-script-sources.lock` instance with its source readers.

Supported v16 verbs are `login-open`, `login-submit` with the closed owned,
invalid or delayed fixture-account role, `login-cancel`, `logout`,
`release-stale-response` and up to three `restart-app` boundaries. Each normal
input uses the existing controls and actual current control tokens. Credentials
are retrieved privately from the reader's account provider, passed directly to
the normal fields and omitted from every host intent, result and diagnostic.
The temporary credential dictionary is dropped after delivery. Python does not
promise erasure of immutable strings or the native text fields; normal view
cleanup remains necessary.

The File-menu logout route is separately documented in
[NORMAL_ACCOUNT_MENU.md](NORMAL_ACCOUNT_MENU.md). Fixture activation already
owns delayed-response release: the adapter deliberately does not send a second
backend mutation for `release-stale-response`. Fresh original observations must
still prove actual issued stale authority and the unchanged new consumer.

Every transaction persists its exact ticket/input and original pre-input native
barrier before input. Each nested normal tap/field action persists fresh native
and UI metadata again, with the 30-second whole-input budget checked before
delivery. A completed duplicate rechecks current admission without input.
Different arguments for a used ticket, interrupted normal delivery or changed
scope fail and retain intent. Once delivery is durably recorded, a retry may
acquire only fresh readiness observations; it cannot refill or resubmit fields.

## Native completion and independent success

Normal submit needs one new original `login-reply` in the current credential
generation after the actual Submit barrier. Signals, HTTP ACKs or an old reply
with a new sampler cursor do not satisfy it. Cached principal readiness is
awaited separately because token adoption and profile loading are asynchronous.
The actual HTTP status is preserved, never inferred from the requested role.

Delayed submit needs the original provider's unique held request for the actual
submit ticket, plus the native pending request and absent local credentials.
Cancel and reopen must preserve that request. View dismissal cannot claim
native cancellation. Logout needs a new `logout-complete`, advanced credential
generation, empty cached principal, no pending request and absent access/refresh
credentials. Menu-row disappearance alone is insufficient. Releasing a retired
response must not adopt or clear any new-consumer credentials.

Readiness is bounded to 20 seconds inside the whole-input budget. Every pending
or final native frame is persisted before the causal decision. Missing,
duplicate, foreign, pre-barrier or rewritten events cannot be retried as input.
All these checks remain prerequisites: fresh protected HTTP/UI/provider and
independent actor observations are still required for full feature success.

## Explicit restart and cleanup obligations

Each of the three restarts has its own `RestartInputs` journal and requires all
primary/actor protected-request and observer-origin leases retired first. Stop
and launch are each durably issued once through normal SDK operations. Launch
requires an independent current OS stopped-state query using the original SDK;
there is no session repair, installation or implicit launch fallback.

The new original process must have a different PID, native Test birth and
AccountManager birth, actual persisted lifecycle counters, the same candidate/
target/SDK binding, and a fresh original kernel ESRCH observation for the old
PID. Original extra background counts are retained. An unknown permission error
does not prove death. Lost stop/launch returns may resume only the existing
durable phase, with no redelivery. All three original proofs remain private
archives for independent role handoff and final whole-run retirement.

General adapter cleanup attempts its normal base teardown, but refuses green
while any input, process-stage source or restart journal remains. It does not
delete such provenance to report success. The full feature owner still must
join both roles' own old/new process histories, publish independent facts,
observe native/UI/remote authority absence, and retire the known host journals
with restart-safe cleanup. The full feature now supplies those checks; the
input components alone do not claim them.

`test_authentication_actions.py` has eighteen synthetic SDK/native/OS cases,
including ordinary invalid/owned login, pending cancel/reopen, real menu input,
three restarts, retained leases, lost returns, ignored submit/logout/stop,
unknown kernel proof, deadline expiry and journal corruption.
`test_authentication_causality.py` adds fourteen original-event counterexamples.
The existing concrete adapter tests cover stopped-state admission and cleanup
guards. These tests execute no APK or device.

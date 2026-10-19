# Normal login controls, version 1

This E2E-only source primitive extends the existing NormalControlUi dispatcher.
It identifies the actual PhoneLoginBody and its real username/password, Submit,
Cancel and TabletHome login controls. It does not implement a full feature
adapter, native logout, startup configuration, permissions or device qualification.
The generic/Pico/iOS login surfaces are not yet recognized by this profile.
Native source is uncompiled and unexecuted.

Admission requires OVERTE_E2E_FEATURE_TESTS, --testScript, the actual GUI thread,
a source-bound original Qt root/window and a fresh passive AccountManager sample
read on its owner thread. LoginUiContext accepts the actual observation v1,
positive original credential generation, endpoint identity and current pending/
token flags. It never calls isLoggedIn(), refresh, login, logout or a URL setter.
It rejects absent or older-than-1500ms samples and unknown endpoints. Original
native/client epochs remain distinct from iOS host epochs.

## Wire and metadata

NormalControlUi's existing schemaVersion, instance, generation, sourceSequence,
lastCommandSequence, elapsedMs, capturedEpochMs, processId, ready and controls
fields are unchanged. Login observations add loginControlsVersion:1 in place of
the other surface version. Row fields are exactly id, token, enabled, focused,
inputReady; login.page additionally has profile:"phone-login-v1", domain,
waiting, closing, error, accountInstance, credentialGeneration, endpointSha256,
nativePending and tokenPresent. The six closed IDs are login.entry, login.page,
login.username, login.password, login.submit and login.cancel.

Domain/waiting/closing are actual QML properties. Native pending is independently
read from AccountManager; transient UI/native disagreement is observed rather
than repaired. The original single PhoneLoginError label maps its actual empty
text to none and translated incorrect-credentials text to invalid-credentials;
other text maps to other without exporting it. Missing/ambiguous labels are
unavailable. No username/password, length or credential digest is returned.

The host parser rejects unknown/missing fields, duplicates, non-booleans, lost or
changed native/UI identities and regressing credential generation. Before secret
input it pins the actual endpoint SHA to the controlled HTTPS origin (or its
native root-slash spelling); no expected principal or result is accepted.
Source control tokens include original object identity, page/native state and
credential context. Native dispatch re-observes these before consuming intent.
A changed endpoint, active token, native pending request, domain dialog, closing
page, disabled/stale/occluded control or wrong focus refuses credential input.
Cancel deliberately remains actionable during pending login. View close is not
a network abort. Only the independently measured full journey can judge that.

Commands retain exactly schemaVersion:1, commandId, instance, generation,
sequence, observedElapsedMs, controlId, controlToken and action. Actions are
activate, replace and submit; replace additionally has text and is restricted to
the two credential fields. Submit is normal Return on the focused password
field. Credentials must be nonempty printable ASCII with at most 4096 UTF-16
units. They travel only in the existing private input channel. Do not copy the
request into public receipts, exceptions or reports. Input receipts contain
only the existing closed delivery metadata and never echo text.

Native actions enter the actual Qt window through ordinary pointer/key/IME
input. Existing NativeFieldInput verifies the actual focused editor after a
replacement; it does not assign a text property or invoke a QML function.
Tokens/sequence are consumed before dispatch; uncertain mutations are never
replayed. The existing five-second source/command budget and bounded reads apply
in concrete platform transports. The token recipe uses at most 101 reads over
ten seconds per view/focus wait, bounded even with a stalled clock. A 300ms
stable absence is required after Cancel, including idempotent already-closed
cases. No login outcome is inferred from input delivery, focus or view absence.

## Ownership and remaining composition

TokenLoginUI requires the owner to persist intent **before every input**. The
callback receives only closed verb, fresh original UI metadata and control ID,
never credentials. It does not create or retire the full run ownership scope.
The complete owner must admit a controlled baseline, retain uncertain input,
close only its own view, observe actual protected anonymous/account state,
release all native probe/origin resources and verify fresh file/authority
absence before deleting its journal. A lost process cannot silently discard
that work; intentional restart requires the separately verified new binding.

The UI recipe accepts only the private fixture username e2e-<owned-run> and its
actual bounded credential pair. It can open/reopen the normal view, fill fields,
deliver normal Return and close the view. It cannot set pending, error, principal
or a desired result. After submission, independent actual native profile/UI and
backend witnesses must establish success/failure. Full lifecycle/logout/remote
actor composition and trusted native fixture origin remain prerequisites; no
feature.authentication operation is advertised by this primitive.

Eleven device-free recipe checks cover ignored open/focus/close, pending view
close/reopen, lost intent/response, foreign domain/endpoint/account/UI sources,
context regression, malformed/secret fields, wrong private credentials and
bounded clocks. They exercise a synthetic widget boundary only. Native field
input, translated labels, actual geometry, TLS and every client remain untested
on devices.

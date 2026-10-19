# Normal login controls, version 2

This E2E-only source primitive extends the existing NormalControlUi dispatcher.
It identifies the actual PhoneLoginBody and its real username/password, Submit,
Cancel and TabletHome login controls. It does not implement a full feature
adapter, native logout, startup configuration, permissions or device qualification.
Version 2 additionally recognizes the reviewed generic QML login credentials,
pending and completion bodies for later Pico/iOS transport integration. These
platform transports and full Authentication remain incomplete. Native source is
uncompiled and unexecuted; no recognized profile is device qualified.

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
fields are unchanged. Login observations add loginControlsVersion:2 in place of
the other surface version. Row fields are exactly id, token, enabled, focused,
inputReady; login.page additionally has profile (phone-login-v1 or qml-login-v1),
stage (credentials, pending or completion), submitEndpointSha256, domain, waiting,
closing, error, accountInstance, credentialGeneration, endpointSha256,
nativePending and tokenPresent. Closed IDs are login.entry, login.page,
login.username, login.password, login.submit, login.cancel and login.server.
Native/UI tokens retain their actual original hex or UUID spelling. Transport
adapters must validate that spelling before input; it does not prove identity.

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

Generic QML identities are read through the actual component QQmlContext's public
nameForObject API, including enclosing Controls contexts; no objectName is added
to product QML. Root/body/label discovery is bounded to 4096 items/depth 128 and
ambiguous or unsupported social/domain bodies are unavailable. The actual visible
loginErrorMessage label distinguishes the generic incorrect-credentials message.
The actual loading spinner distinguishes pending from completion. Missing body/
label/context cannot become anonymous success or empty error.

The generic page has a real metaverseServerField. Its independently observed
supported HTTPS origin yields submitEndpointSha256; invalid/empty/credential-bearing
URLs yield the empty digest and cannot authorize secret input. Phone has no such
field and retains the actual native endpoint digest. Native context and generic
submission target must both match the controlled origin before credentials.
The recipe may edit the server through ordinary field focus/IME and focus loss,
then requires actual target/native agreement. An ignored edit cannot release
credentials. This setup is an owned preference change: the full coordinator must
retain/restore its actual original private configuration. It does not silently
redirect a preexisting real account. Native controlled origin must already be
established before recipe admission; missing trusted fixture setup stays closed.

Generic tablet pending pages have no Cancel button. An owning platform may
supply close_view using its separately bound actual ordinary tablet navigation
(e.g. Home), with intent persisted before that input. The recipe then requires
fresh stable page absence, without claiming a network abort. Startup login on a
separate WebEntity/overlay needs its own actual surface/input binding; it cannot
borrow tablet navigation or report absence by inspecting the wrong root. For the
generic profile closing=false describes an actual alive/visible root, not a
product closing transaction; hidden/destroyed roots disappear. Full observers
still need actual root/surface ownership and independent lifecycle evidence.

Commands retain exactly schemaVersion:1, commandId, instance, generation,
sequence, observedElapsedMs, controlId, controlToken and action. Actions are
activate, replace and submit; replace additionally has text and is restricted to
the two credential fields and the generic server field. Submit is normal Return on the focused password
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

Sixteen device-free recipe checks cover ignored open/focus/close, pending view
close/reopen, lost intent/response, foreign domain/endpoint/account/UI sources,
context regression, malformed/secret fields, wrong private credentials and
bounded clocks, native/server target disagreement and ignored generic server/
navigation inputs. They exercise a synthetic widget boundary only. Native field
input, translated labels, actual geometry, TLS and every client remain untested
on devices.

Version 1 did not carry stage/submission-target facts and recognized only Phone.
No full area producer was qualified. Registry/readers now accept only version 2;
version 1 remains in Git history. Observation schemaVersion and command wire
schemaVersion stay 1; common feature contract stays 6. Phone's separate mandatory
privateCommandReaderVersion:1 is unchanged by this control metadata migration.

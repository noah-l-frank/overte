# Pico normal login input, version 2 source metadata

`_login_controls(target,intent,run,origin)` composes the existing verified Pico
candidate/OpenXR/normal-Scripts context with the common TokenLoginUI recipe.
It is composed by the explicit [complete Authentication source adapter](AUTHENTICATION_FEATURE.md).
The internal component alone provides no feature verdict or device acceptance.

The actual NavigationUi source collects original generic Qt login roots,
component IDs, visible error label, spinner stage and server field. It reads
passive AccountManager state on its owner thread without starting refresh or
changing authority. The loginControlsVersion:2 marker exists only with a valid
fresh native account context. Missing/legacy contexts, unknown or ambiguous
components and unsupported domain/social pages stay unavailable.

The existing navigation snapshot/command transport keeps its schemaVersion:1,
original bridgeId/generation UUIDs, PID/start/candidate/OpenXR binding, original
elapsed/device epochs, sequence and original control tokens. Login rows use the
shared [version 2 metadata contract](../../native/NORMAL_LOGIN_CONTROLS.md).
PicoLoginIO validates the entire original snapshot before selecting its actual
login rows. It rejects regressing device epochs. It does not manufacture a
principal, error, pending flag or desired target from input arguments.

Actual NativeFieldInput and the existing VR surface pointer path deliver normal
focus, IME replacement and Return. Before credentials, both original native
endpoint and actual generic server-field target must match the controlled HTTPS
origin. The full Pico recipe refuses a foreign target before credentials and does not
edit a saved server preference; the process-only fixture origin must already
supply the normal generic page target. No direct QML login
handler, AccountManager mutation, preference setter or TLS override is a test
input. The private fixture username is e2e-<run>, with its actual private password.

The ordinary tablet pending body has no cancel control. The component persists
login-close intent, then the full Pico recipe observes the actual HMD Home
entity and sends one ordinary OpenXR trigger ray through the existing controller
dispatcher. Home has no assumed generic QML row. Actual page absence remains
stable for 300ms; the native account request continues. Reopening uses ordinary
login input without another submit. The preexisting E2eLauncherActivityBase
supplies --no-login-suggestion, honored by Application_Setup.cpp. The separate
passive startupDialogPresent source must nevertheless read false; an actual
startup LoginDialogEntity causes refusal rather than an invented dismissal.

## Private command cleanup and ownership

The native navigation bridge reads its private JSON directly rather than through
a CommonJS cache. After every confirmed or uncertain replacement, the host
replaces only its bound fixed navigation-ui-command.json with an empty object.
Native ignores its absent identity, without replay or product mutation. The
existing atomic writer verifies its original replacement bytes and a separate
fresh read additionally requires exactly the empty object plus newline. An ACK
with retained text therefore fails. Source/candidate/process loss prevents
foreign file cleanup and retains caller intent. No raw text is saved in status
or ordinary ownership observations; public errors are closed codes.

The mandatory callback records original metadata and input intent before every
input; credentials never enter it. The full owner adds native/provider/protected
proof, normal menu logout, old-PID exit, separate publisher and release/quiet
obligations described in the Authentication handoff. Canonical installation and
OpenXR guards remain mandatory. No native source or VR input has been compiled
or exercised on a device in this session.

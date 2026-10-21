# iOS Authentication source packet

The full iOS Authentication adapter composes the existing candidate, native
transport, normal Login/Menu input, private AFC carrier, account history and
controlled HTTPS provider. The unchanged seventeen-step shared journey runs on
synthetic iOS SDK boundaries with a real local HTTPS OAuth/profile server.
Native additions remain uncompiled; all devices remain untested. Source and
host completion do not establish iOS product functionality.

`IOSLoginSource` reads a new original native HTTP/AFC receipt, retains its full
body, original iOS nonce, native epoch, actual transport and root/window UUIDs,
source sequence, elapsed clock and input cursor. It projects only original
Login controls and validates the projection against that exact receipt. A real
tablet visibility/window generation transition is retained, without resetting
transport/source/input continuity. Per-input `TokenLoginUI` separately pins the
active generation and control tokens. Read-only samplers refuse input methods.
Credentials still require the existing private AFC lease; they never enter the
public normal-input HTTP channel.

The E2E-only `NormalAccountMenuControls.h` observes actual
`TabletMenuItem.qml` delegates and their current visible/enabled QAction/menu
source. Source pointer plus original label hash retires tokens when a delegate
is reused. The normal iOS input receiver exposes File/logout controls with
versioned type/label metadata and checks actual source and hit ownership again
before ordinary pointer delivery. It invokes no QAction, QML handler, account
setter or preferred outcome. The input adapter requires the owned native
principal and endpoint before each click, journals original input intent, and
returns delivery only. Native credential/history, protected access and provider
proof must independently establish the effect.

`HIFI_METAVERSE_URL` is the product's existing process environment override in
`libraries/networking/src/MetaverseAPI.cpp`; no Android launcher or new endpoint
setter is imported. `AccountPreferenceObservation.h` passively records the actual preference's
presence, QVariant type and value digest, together with the actual process
override digest. It reads no credentials and performs no setting mutation.
The generic form writes its Directory Server preference during every login,
and exposes no ordinary UI operation to restore an originally absent key.
Consequently the full owner requires a dedicated test sandbox whose existing
string preference and process override both already equal the owned fixture
origin. Missing, differently typed, foreign or unconfigured originals fail
before input. This explicit environment prerequisite avoids modifying an
unrelated preference or inventing restoration. Native/actor cleanup must
independently re-read the same original facts before retiring ownership.

The native UIKit E2E mirror exposes the original token as `accessibilityValue`
for every `account.*` control, just as it does for Login/Script/Graphics
controls. A replaced Qt token retires the old UIKit proxy. Ordinary WebDriver
token checks therefore reach the original File/logout/Remember control, with
native source/hit checks repeated before pointer delivery. This Objective-C++
bridge remains uncompiled and untested on devices, like the other native
additions; synthetic SDK token reads cannot qualify the actual UIKit bridge.

The full owner also preserves the original `keepMeLoggedIn` boolean and
`keepMeLoggedIn/savedUsername` string. Both must already exist; the saved
username must initially be empty. During the run only empty or the owned
username digest is admitted. Foreign, absent or differently typed originals
fail before normal input. Original snapshots retain receipt, actual PID,
candidate and session identity across all three process replacements.

The secret-free `clear-login-username` input accepts no text or credential
bytes, and uses ordinary focused-field IME replacement with an empty string.
It rechecks the original field token, current Login context, focus and hit
ownership. Actual checkbox metadata is tied to the current generic Login
page/account source; clicks are refused during a pending/native-token state.
Cleanup first drains the private credential carrier, then cancels/logs out
normally, clears the username and restores the measured Remember boolean via
normal checkbox input. Fresh primary, actor and finalizer originals must all
show the exact initial preference snapshot before evidence retirement.

## Operation and lifetime composition

`feature.authentication.act`, `.observe` and `.cleanup` use the existing shared
contract v16 and its normal Login/cancel/invalid/delayed/restart/logout verbs.
`authentication_actions.py` persists one-send intents before input and retains
uncertain delivery. `authentication_causality.py` joins actual native account
history and credential generations to each operation. Closing the view does
not cancel a native request. Delayed grants are released by the fixture owner
only after an actual old-PID absence and new native process/account birth.

`authentication_samples.py` independently acquires Login/tablet/native account,
protected HTTP probe, original origin-file and provider originals for each
role. The actor additionally requires the server's original matching protected
request proof. Each acquisition releases its own probe, files and callbacks.
Immutable compressed ledgers retain source prefixes and failed-reading intent.
The clock join brackets untouched original native packets with fresh native
fences and host UTC/monotonic acquisition clocks; no AFC timestamp or requested
source version is treated as freshness. Public samples use the actual bounded
host acquisition start, with the common 1.5-second freshness and stable/quiet
windows. Native clocks remain native, including tested one-day host skew.

`authentication_feature.py` coordinates the run, three restarts, separate actor
publication, repeatable cleanup and hash-checked final retirement. The source
lock is shared with Scripts because they use the same native source channels.
Cleanup proves at least three seconds of original anonymous/no-request/no-view
state, restored preferences and drained carriers/probes/files. The runner must
separately close its HTTPS account fixture; finalization fails and preserves
responsibility until actual provider authority/requests/tokens are absent.
Only then are role/stage transcripts retired under a recoverable hash plan.

## Explicit admission and independent observer

The private `OVERTE_IOS_FEATURE_ADAPTER_CONFIG` schema remains version 1.
`areas` may select `authentication`, `scripts` or both without duplicates. The
existing `fixtureConfig` points to the private adapter-only reader config; it
cannot publish actor facts or mutate the provider. Authentication additionally
requires a canonical HTTPS `testBuild.launchEnvironment.HIFI_METAVERSE_URL`,
the same dedicated native preference origin, the original preference v2 and
clear-input hooks, and the canonical full installed-candidate gate.

`ios/authentication_observer.py` is the separately invoked actor process, with
private version-1 keys `iosAuthenticationObserverVersion`, `target`,
`candidateArguments`, `fixtureUrl`, `actorToken`, `durationSeconds` (30–1800).
It reuses the existing candidate/session source runtime and bounded observer
loop, never creates a session or performs normal input. The primary never
starts this worker. Deployment/execution belongs to the Proxmox laboratory
after separately authorized compilation and qualification. No worker runs here.

## Integration and verification limits

Pure Authentication decomposition is derived from frozen Phone
`fe4684bf46585088370b3a328a738f147e670b97`; iOS process/environment, UUID/nonces,
UIKit/Qt controls, AFC storage/private carrier and original clocks are native
iOS implementations. No Phone launcher, ADB or Android ownership is imported.
New local contracts are iOS Authentication actions v2, samples v3, feature/
causality/observer v1, native preferences v2 (reader v1 retained), and the
secret-free iOS clear-input/Remember-control v1 extensions. Shared journey and
public operation schemas remain unchanged. Preserve these additions when
reconciling registry unions with parallel Phone/Pico work.

Host regressions cover the full journey and separate original actor/server
proof, ignored submit without resend, original authority still present, exact
preference restoration, ignored clear, stale/foreign/modified originals, wrong
process, unowned saved usernames and canonical candidate replacement. They
exercise real temporary files and loopback HTTPS at synthetic SDK/native
boundaries. Compilation, UIKit/Qt behavior on a device, signed candidate bytes,
OS process behavior and actual Proxmox/device acceptance remain unverified.

The completed packet passed 515 selected iOS host cases and 1037 shared quick
control-plane cases with zero failures, errors, skips or blocked subprocess
attempts. The no-build selector explicitly excludes twenty iOS and three shared
compiler cases; these were not executed. Five applicable project suites also
passed: documentation, documentation-contracts, ios-input-selection,
policy-consistency and project-coverage. Commands use the existing unittest
entrypoints under a subprocess audit that refuses compiler/build/device/Jenkins
programs; only the reviewed synthetic SDK stub is permitted. `git diff --check`
and the contract registry validator passed.

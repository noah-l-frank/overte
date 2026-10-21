# Pico Authentication source adapter

`feature.authentication.act/observe/cleanup` composes the unchanged catalog,
OverteSession and common v16 17-step journey. This is source implementation and
host-model verification only: native code is uncompiled and device runs are zero.
The remaining area gaps stay visible in the [coverage matrix](FEATURE_COVERAGE_20261021.json).

## Admission and operations

The exact source/artifact/signer candidate, installed bytes, foreground PID/start
and existing OpenXR session must already be bound. Nothing discovers, launches
or repairs a target during observation. These explicit settings are required:

- `OVERTE_ANDROID_E2E_DEBUG=1`, `OVERTE_PICO_OPENXR_INPUT=1`,
  `OVERTE_PICO_NORMAL_SCRIPTS=1` and its existing controlled scene URL.
- `OVERTE_PICO_ACCOUNT_FIXTURE=1`, `OVERTE_PICO_FEATURE_AUTHENTICATION=1`.
- `OVERTE_E2E_FEATURE_FIXTURE_URL` is the owned HTTPS `/feature-fixture/v1`
  provider; private `OVERTE_PICO_FEATURE_FIXTURE_CONFIG` is the existing
  mode-0600 adapter-access contract. A runner reader token is refused.

The existing debug launcher receives only the strictly validated HTTPS origin
extra `org.overte.e2e.ACCOUNT_ORIGIN`. Before Qt starts it sets the process-only
`HIFI_METAVERSE_URL`. It does not rewrite saved endpoint preferences, install a
CA or disable TLS. The future Proxmox owner must provision ordinary trusted
fixture HTTPS separately. The inherited `--no-login-suggestion` launch argument
already suppresses startup suggestion; a separately observed actual startup
dialog still fails admission. Generic QML server-target mismatch refuses input.

`login-open`, invalid/owned/delayed `login-submit`, `login-cancel`, three
`restart-app` boundaries, fixture-owned `release-stale-response` and `logout`
use the existing closed verbs. The adapter never reissues provider activation.
Login uses original native field tokens, focus, IME replacement and Return on
the actual VR offscreen surface. Credentials are transient and private command
replacement is independently read back empty even after uncertain delivery.
Normal File-menu delegates perform logout; no QAction or account setter is a
test input. Each delegate token includes actual current account context.

## Actual VR Home input

The generic Login/Menu pages have no assumed `nav.home` QML control. A separate
nonce-only native source reads actual `HMD.homeButtonID`, tablet parent, local
Gizmo identity, world position, visibility/pickability, head position,
sensor-to-world matrix and `TabletProxy::onHomeScreen()`. It cannot mutate any
of them. Positive uniform affine tracking transforms and bounded STAGE poses
are validated, using the existing right-hand grip calibration.

After durable original intent, one existing `input.primary` grant aims the
controller ray at that observed entity. The production dispatcher handles its
normal Primary release and Home message. No message emission, direct Qt slot,
QML method or `gotoHomeScreen` invocation is test input. A delivery ACK does
not prove Home: a fresh same-process, same-entity original Home transition must
arrive within eight seconds. Already Home requires no gesture (which would
otherwise close the tablet). Cleanup uses Home before ordinary controller close.

## Original observations, independent actor and restart

Each primary/actor sample independently acquires native AccountManager event
history, protected HTTPS reply, passive login metadata and weak whole-tree
login/menu inventory, actual QML component/callback inventory, original VR
keyboard state, native origin/probe owners and current tablet inventory.
The actor separately joins its protected request ID to original backend proof.
The provider records the actual held request and ticket, release and issued old
authority. Post-restart consumer anonymity and lingering old server authority
are separate facts; closing a page never proves native request cancellation.

The separate publisher is `pico4/feature_observer.py --config <private-file>`.
Its version-1 config contains `area: authentication`, original target/candidate
arguments, HTTPS fixture URL, actor token and bounded duration. It uses a
separate Client/process and the already-bound candidate. It can publish or wait
for an explicit pending transaction; it cannot activate runs, deliver input,
discover devices, relaunch or repair. Run it only under future Proxmox ownership.

Every restart records stop and launch intent once. Both roles independently
require original old-PID ESRCH, new native/account birth, same candidate/target
and nonregressing lifecycle. Lost launch recovery observes those facts and
binds the host session once; it never sends launch again or repairs the SDK.
The real Pico bridge UUID may rotate with the process.

## Cleanup, limits and recovery

Private neutral journals live in the Authentication target namespace, with one
cross-process source lock. Neither old Phone journals nor another run's owners
are adopted. Input intent precedes every UI/controller grant. Uncertain submit,
Home and logout are retained and never resent, including cleanup. If logout
has an unresolved original delivery, cleanup waits only for its native result;
missing revocation keeps ownership and fails.

Provider grants must be disabled, held/inflight handlers drained and remote
authority revoked. Ordinary owned logout/page close must leave native anonymous
protected access and no tokens/pending request. Weak original login/menu roots
remain resources while hidden or detached. Actual menu Timer.running and
retained menuItem are observed; disappearance from visible controls cannot
retire either. The native OffscreenSurface also weakly tracks every original
QQmlComponent load and its real statusChanged continuation. Constructing,
loading, finishing and finished-but-not-destroyed components remain resources;
only original QObject destruction retires their identities. Actual Keyboard
raised state is independently read under its existing lock. No callback is
cancelled, component destroyed or keyboard state changed by instrumentation.
Only actual QObject destruction retires a root identity.
Bounded original inventories fail closed on incomplete traversal/history.

Native origin/probe leases and original files must be independently released
and absent. Both roles require a minimum three-second quiet baseline. Final
provider run retirement and hash-owned journal removal follow those proofs;
errors retain unresolved owners. The established source/UI/input budgets are
unchanged (native request five seconds, login UI ten, action thirty); Home is
eight seconds. Sources retain at most 4,096 nonces, 16 roots and 256 root retirements; native
QML load history permits 128 live components and 1,024 retirements. Exhaustion
or a changed/forgotten original component fails closed.

The owning no-build Pico groups cover the full common flow plus ignored input,
foreign origin, missing native grant, uncertain Home/submit/logout, lost launch,
hidden detached roots, pending menu/QML callbacks and a retained VR keyboard. Pure geometry tests
independently verify the calibrated ray across tracking rotations. Synthetic
Qt, native, OS, HTTPS and OpenXR seams validate host logic, never product behavior.

Shared extractions and original hashes are in
[PROVENANCE.json](../authentication_journey/PROVENANCE.json). Phone/iOS files
remain unchanged. Reconcile neutral journals, the default-empty Android launcher
hook and shared publisher loop explicitly when integrating the parallel branch.

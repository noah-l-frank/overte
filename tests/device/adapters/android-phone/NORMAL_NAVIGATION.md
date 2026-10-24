# Normal Phone Go To and Places history

The bound Phone Appium wrapper implements `places.open`, `places.goto`,
`places.back`, `places.forward` and `places.close` through normal native W3C
accessibility input. This is local implementation; no device qualification or
native application build is claimed. Shared/unbound diagnostics do not advertise
the new operations. No current private target configuration is modified here.

An explicitly configured controlled physical Phone target may opt in with:

```json
{
  "normalNavigation": {
    "contractVersion": 1,
    "profile": "phone-native-v1",
    "sceneUrl": "http://reachable-owned-fixture:18080/scene.json"
  }
}
```

Place this object under the existing private `controls`. Preserve the original
controlled Phone `scene`, run-as `probe` and `clientControl` configuration.
The configured scene URL must match the actual owned scene fixture. Use an
external fixture or a matching fixed host/port for provider `auto`; a random
different origin is rejected before UI input. Only that scene's three fixed
viewpoint URLs can be entered. No arbitrary URL or locator recipe is accepted.

The existing SH009 candidate verifier and actual installed-APK association remain
mandatory for these capabilities. Native preflight runs around session creation,
the complete operation and the same process/foreground guard used around native
element reads and input. The result stays exactly `performed: true`; the normal
navigation journey independently judges actual scene/viewpoint/render effects.

The flow uses the source-reviewed `Go to destination` toolbar accessibility name,
the actual `PhoneAddressField` and Go/Cancel IDs, the normal tablet entry and
its PLACES application button. Back/Forward use the real `goBack`/`goForward`
Places controls; Phone's smaller address dialog has no Forward button. Reopening
a closed tablet can restore a previous page, so normal Home is used when needed.
There are no direct AddressManager calls, QML messages, probe navigation commands
or coordinate fallbacks.

Before opening, the flow refuses pre-existing unowned address/tablet panels.
Opening intent is saved before the native click in the original private atomic
session state. That ownership is bound to its actual process and independently
verified source/artifact. Partial failures retain cleanup intent for the next
CLI invocation. Owned controls are closed through Cancel or normal tablet Close,
and stable real element absence is observed. Disabled fields still require
actual disappearance. Repeated close is idempotent and leaves unrelated panels
untouched. Changed ownership fails; original overall Appium cleanup remains
available without a still-valid candidate and clears the original private state.

The Main host checks execute the real flow, input primitives and navigation
journey with only native W3C/probe/time/guard boundaries substituted. The real
Phone candidate wrapper must additionally be verified against a composed in-tree
Phone verifier source. Main alone does not contain that native verifier; an
external reference tree or stub import cannot qualify the wrapper. Keep this
pending distinction until the Phone-layer verification receipt is recorded.


The `scene.load` foundation can also submit precisely that configured HTTP(S)
base scene through the same normal Go To UI. Its URL must exactly match both
`controls.normalNavigation.sceneUrl` and `OVERTE_E2E_SCENE_URL`, without a
viewpoint query. The bound controlled debug Phone, verified installed candidate,
original foreground process and persisted normal-panel ownership remain
mandatory. The existing embedded-fixture path and Places viewpoint grammar are
unchanged. When the full Navigation extension is enabled, fresh provider inputs
must also match the actual source revision, scene URL, native endpoint and
native protocol signature before any UI input.

The result is only `requested: true`. It deliberately supplies no marker-only
verification hint: `OverteSession` must independently observe the actual HTTP
scene URL and native readiness. The unmodified domain-roundtrip module must
observe real domain departure and reconnection in the original process; the
Places module must then observe the same controlled HTTP scene and viewpoints.
An ignored normal Go input may return an ACK but cannot establish arrival.
The original private panel lease supports partial cleanup after an interrupted
input. Host SDK/kernel/provider producers are explicit seams; no Android or
physical acceptance is implied.

The bound Phone `navigation.enter-domain` foundation uses this same version 1
normal editor profile. It never falls back to the app-private Android command
file. Before creating an SDK session or sending input, the adapter validates a
credential-free `hifi` URL with an explicit port from 1 through 65535, no query
or fragment, no whitespace/control characters, and at most 2048 characters.
The complete input must equal `OVERTE_E2E_DOMAIN_URL`; its hostname must equal
`OVERTE_E2E_DOMAIN_HOST` case-insensitively. These are infrastructure inputs from
the independently verified current controlled-domain fixture, not observed
client state. The existing `OverteSession` domain configuration, current-owner
preflight, UUID/marker checks and independent effect observations remain required.

The flow types the exact URL into the ordinary address editor, reads the actual
field text back before Go, and observes the editor disappear. Existing process,
session, installed candidate and private panel-ownership guards surround all
input. The only result is `requested: true`; it does not assert connection,
arrival, markers or pose. Ignored Go input must remain a failure in the original
fresh domain-probe checks. A missing/foreign normal profile or unbound domain
input fails before input, and changed process ownership prevents further clicks.
This is host adapter/test logic; real Phone behavior requires a separate device
run on the explicitly bound client APK and host source revision.

The `scene.load` and `navigation.enter-domain` normal editor flows use the
existing supported 20-second native UI bound. Other normal navigation operations
retain 10 seconds. Every actual lookup still runs its complete fresh continuity
checks; stable disappearance still requires two fresh absent observations at
least 0.3 seconds apart. Inputs are sent once, with no retry or cached fact.
This bound accounts for elapsed process/installed-candidate checks: a first
absence near a 10-second deadline otherwise leaves no time for its independent
confirmation. A host latency counter proves that scheduling case and keeps an
ignored Go or foreign process red. Job15 did not retain element response values,
so this calibration does not establish its device root cause or a successful
navigation. Original outer-operation and module bounds remain independently
enforced; a fresh device retest must establish the actual effect.

`probe.snapshot` requires the SDK session already owned by an explicit launch.
Every Phone observation retains that session, generation, target, installed
candidate and native PID/start identity across the original fresh probe reader.
It cannot bootstrap, rebind, repair or replace a missing/dead SDK session; that
condition is an error. The common operation and result schemas are unchanged.

Before a normal Go submission, Phone reads a fresh bounded Android
`dumpsys input_method` observation through its mapped transport. Exactly one
explicit valid `mInputShown` header is required; missing, malformed, ambiguous or
oversized output is an error. A shown keyboard permits one `hide_keyboard` SDK
request, followed by fresh exact address text and native hidden-state checks
under the same session/process/candidate guards. No acknowledgment proves
visibility or navigation. This guards possible keyboard occlusion; actual17 did
not establish that cause. No input replay, coordinate tap or timeout extension
is added. Other clients and common operation/result schemas are unchanged.

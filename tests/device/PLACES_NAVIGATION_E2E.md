# Normal Go To and history

`places-navigation-parity` enters three viewpoints in the owned HTTP scene
through normal Go To, then visits both history directions. Actual probe reads
must show the matching full scene URL, grounded feet position, all five owned
scene markers and advancing recent renderer presentation. A displayed address
or `performed: true` alone cannot qualify. The source-bound Phone Appium adapter
advertises these operations only with its explicit `phone-native-v1` profile,
controlled scene and verified installed candidate. iOS and Pico native input
activation and physical-device acceptance remain pending.

## Native input contract

- `places.open`: open the actual Go To or Places entry from the normal client
  toolbar/tablet.
- `places.goto {url}`: open/reopen the real address editor, enter the exact
  controlled URL and activate its normal Go control. History is never written
  directly and a probe navigation command is never substituted for UI input.
- `places.back {}` and `places.forward {}`: open/reopen normal history controls
  as necessary and activate the actual enabled Back/Forward control.
- `places.close {}`: dismiss only the owned Go To/Places panel and dialogs,
  including after partial input failures. This cleanup remains possible after
  a process-continuity assertion fails.

All five operations confirm only `performed: true`. Unknown actions, extra
arguments, direct API calls and navigation verdicts in their result are rejected.
The existing Phone address dialog and native Places implementations provide
platform-appropriate controls; no hidden QML bridge or injected script drives
them. iOS/tablet and Pico bindings still require their native input work.

The common tablet address editor exposes stable object names
`tabletAddressDialog`, `tabletAddressLine`, `tabletAddressHome`,
`tabletAddressBack` and `tabletAddressForward`. These identify actual controls;
they do not provide feature mutation or verdict APIs. `NativeFieldInput` accepts
only an already focused, visible, enabled editor on its owned Qt Quick window.
It uses normal Select All, input-method commit and Return events, with fresh
editor/focus observations after replacement. A successful Return reports event
delivery only. Navigation must still pass the independent scene observations.

The existing registered `device-control-plane-full` tablet close check executes
the actual shared implementation against real Quick Controls editors. Its
`NativeFieldInputTests` class can also be run separately with
`OVERTE_NATIVE_QT_MAJOR=5` or `6`. A relocated Qt 5 host SDK may be selected using
`OVERTE_QT5_HOST_ROOT`; all application source and headers still come from the
current checkout. These are hardware-free behavioral checks, not application
builds or native-device acceptance.

## Exact fixture and state

The suite uses the existing owned `scene` fixture. Its environment must provide
the real reachable HTTP(S) URL ending in `/scene.json`; bundled file URLs or
arbitrary public worlds are not supported by this packet. Provider `auto` may
create the normal scene fixture. External mode requires `OVERTE_E2E_SCENE_URL`
before target discovery.

The three literal location queries use feet viewpoints A `(0,0,4)`, B `(2,0,4)`
and C `(-2,0,4)`, all on the existing floor. Distinct full query URLs make real
serverless history observable. Relative-only path changes would retain the same
serverless address, so this test does not use them as a history oracle. Actual
native AddressManager query semantics were reviewed before defining the inputs.

The module first prepares the ordinary controlled scene. During the test,
`OverteSession.snapshot` validates existing native probe v2 observations and
projects only actual address/domain/avatar/render fields. Expected viewpoints
are never sent to the probe. Every arrival requires at least three new probe
samples spanning half a second, with a new native renderer frame for each,
position error at most 0.75m, speed at most 0.15m/s and grounded non-flight state.
`scene.ready` is not reused as a default-spawn oracle at viewpoints B and C.
Foreign scene URLs, missing geometry, airborne/drifting avatars, stale rendering,
replayed probe samples or process replacement fail.

Cleanup restores A through the same normal Go To controls and independently
observes the restored actual state before closing the owned panel. An ACK-only
restore or cleanup failure prevents success. Partial entry preserves the primary
failure and still attempts owned-panel cleanup. No user bookmark, Home setting,
directory server or unrelated history entry is deleted or rewritten directly.

The packet covers controlled normal Go To and Back/Forward. Bookmark CRUD and
durability, directory search, failed-navigation feedback and external domain
transitions are separate cases. Exact built artifact and installed-code binding
and real platform observations remain necessary for device acceptance.

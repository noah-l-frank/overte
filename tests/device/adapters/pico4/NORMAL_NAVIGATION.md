# Normal Pico VR-tablet Go To and history

The existing `--kind pico --native-binding` adapter supports the five
`places.*` operations only when `OVERTE_PICO_NORMAL_NAVIGATION=1`,
`OVERTE_ANDROID_E2E_DEBUG=1`, `OVERTE_PICO_OPENXR_INPUT=1`, the isolated ADB server
and private OpenXR session state are configured, and `OVERTE_E2E_SCENE_URL`
identifies the owned HTTP scene. All original candidate inputs remain mandatory,
including the exact APK, expected inputs, SH-009 identity, original build tiers,
version/signer expectations and package/network-decoder verification. The
verified archive must actually contain the complete E2E input layer; runtime
opt-in alone cannot activate an ordinary APK. The
unbound generic adapter does not offer this navigation profile.

The suite starts with its fresh controlled process and a closed normal VR
tablet. The adapter persists private source/artifact/process/bridge ownership
before the normal OpenXR tablet-open gesture. It resolves GOTO on the actual
tablet page, using real page-indicator pointer actions as necessary. It then
focuses the real address editor, replaces its text through native Qt key/IME
input, submits Return and uses actual enabled Back/Forward controls. Only the
three configured controlled scene/viewpoint URLs are accepted. HUD toolbar
presentation and an unrelated pre-existing open tablet are outside this profile.

Each native observation and input retains the same live foreground process and
existing OpenXR session identity. Every mutation is bracketed by the original
installed-APK byte comparison. Slow SDK/package verification runs before taking
the fresh input observation; it cannot age that command past the unchanged
five-second native limit. Commands bind the native bridge, surface generation, actual
visible unique control token, observation freshness and increasing input
sequence. An uncertain input is never resent. Native acknowledgements contain
delivery status only; [`PLACES_NAVIGATION_E2E.md`](../../PLACES_NAVIGATION_E2E.md)
independently checks actual scene, grounded arrival and advancing rendering.
The adapter never sends a navigation feature mutation to the probe.

Private ownership persists across the runner's short-lived CLI calls. Cleanup
closes only its own tablet through the ordinary controller route, confirms that
the native tablet is closed and removes its private state. A changed process,
artifact or bridge cannot inherit that ownership. Generic native cleanup remains
available when candidate inputs have become invalid, without issuing an
execution-identity claim. After canonical cleanup confirms force-stop it also
retires the fixed target's leftover navigation intent, allowing the next suite
to start cleanly after a partial failure.

The existing Pico `tablet-e2e-adapter` host case compiles the actual C++ resolver
and shared field implementation against real Qt, and runs the original native
candidate verifier/dispatcher tests with synthetic APK/tool/ADB/Qt-file/OpenXR
boundaries. These are input and binding tests. They do not provide a real APK,
native Android/OpenXR application compilation, a device scene arrival or any
physical acceptance result. Device execution remains a separate later wave.


The private [normal opening composition](NAVIGATION_PREFIX.md) now joins the
original Origin/Home, Places/Directory and first five shared recipe actions
with independently queried primary/actor fields. It retains original journals
and adds no public whole-Navigation capability or final retirement claim.

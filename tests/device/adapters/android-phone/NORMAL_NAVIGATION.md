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

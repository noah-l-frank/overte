# Normal iOS navigation input

Current physical binding: [installed-code binding v1](../INSTALLED_CODE_BINDING.md) guards these
components with actual installed bundle/PID measurements. Legacy simulator and
cleanup-only modes still refuse component access. Historical blanket-refusal
statements below do not describe the new physical path. Complete feature-area
capabilities and device qualification remain absent.

This is an opt-in native UI component profile. It does not establish installed
code identity or qualify a device acceptance result. The canonical candidate
adapter still rejects execution with
`OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE`; neither the IPA hash, process ID,
bundle identifier nor a self-reported source revision substitutes for that join.

The source-selected iOS interface uses the mobile action bar's **GO TO** button
and `+android_phoneInterface/AddressBarDialog.qml`. It does not use Pico's tablet
address editor. History uses the actual native **PLACES** page. The observer
therefore follows both live Qt roots: HUD/dialog and screen-space tablet.

The existing native laboratory target can explicitly select:

```json
{
  "nativeUiObservation": {"kind": "uikit-documents", "version": 1},
  "normalNavigation": {
    "contractVersion": 1,
    "profile": "ios-native-qt-input-v1",
    "sceneUrl": "http://127.0.0.1:18080/scene.json"
  }
}
```

This is a target fragment, not a complete target or permission to discover a
device. A physical E2E build, the existing private test/probe configuration and
the already owned fixture/session are required. Only the three exact controlled
viewpoint URLs produced by `navigation_observation.viewpoint_urls` are accepted.

`IOSNormalUiInput` observes real visible Qt controls and their actual geometry.
E2E-only UIKit buttons project those bounds and carry the current Qt control
token. W3C element clicks deliver normal Qt pointer events. Text replacement
uses Select All and native IME input on the already focused actual editor;
submission uses the normal Go button or an explicit native Return. No text
property assignment, navigation API or external `overteTypeText` command is used
by this profile. A modal address dialog hides the underlying tablet hit targets.
Release builds retain their existing passive accessibility behavior.

The native request has a closed schema, distinct transport/native nonces,
process instance, next sequence, focused field token and a five-second native
freshness limit. The GUI owner publishes an atomic private receipt. Mutations
are never retried. Receipts acknowledge input delivery only; the shared journey
independently judges actual scene/viewpoint, grounding and advancing render
observations. History endpoints may legitimately have one disabled direction.

Panel intent is persisted before opening. A new adapter invocation must match
the original process, native input instance and controlled scene before adopting
that intent. Foreign pre-existing panels are refused. Cleanup closes only owned
panels through actual controls and releases W3C input actions.

Host qualification compiles the actual Qt input producer against both Qt 5 and
Qt 6 and executes the real Python adapter and journey against explicit native
I/O boundaries. It does not compile UIKit or install/run an IPA. The native Mac
build, independent installed-code binding, ordinary device observations and
physical acceptance remain pending.

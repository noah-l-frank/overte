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

The isolated feature-adapter work additionally exercises the connected ordinary
restart coordinator with sources constructed after modeled launch. A fresh SDK,
independent startup bookmark-file load, complete import/tree ledger, navigation,
Places model/HTTP/dialog inventory and UI/reply sources feed the real typed
`NavigationProcessOwner`. The original admission, old process histories and
restart receipts remain byte-for-byte unchanged. One shared modeled import
ledger supplies its own read counter to its two independent source readers;
original clocks and returned native DTOs are never retimed. Ignored startup
bookmark loading leaves the transfer unresolved and never repeats stop/launch.
These two host tests prove source ownership and process-stage coordination.
They do not establish actual iOS restart behavior, whole paired restoration,
compilation or device acceptance. The complete Worlds capability remains gated.

After this transfer, both role-owned observers acquire independent fresh
current-process source groups and immutable rendered PNGs. Their local stage-one
cursors remain original; the whole coordinator derives the public cursor by
adding the actual completed stage-zero observation count. `NavigationPublications`
reopens those original owners and validates both source-floor joins against the
immutable admission and actual typed process context. Its canonical witness
journal keeps the original candidate binding, while each new original reference
explicitly identifies its stage. Existing literal two-field stage-zero references
retain their original interpretation and are never rewritten. A lost accepted
Actor POST is resolved from the actual canonical journal without another POST or
GPU capture; a pending publication blocks the next Actor acquisition. Primary
public reads post no Actor sample. Twenty-four host tests cover the connected
active/restart/publication paths and counterexamples. Paired final restoration
and complete Worlds dispatch remain required before capability advertisement.

The connected current-process test also opens a newly born ordinary Qt Places
page, materializes its real controlled HTTP/JS/QML directory, deletes the actual
persisted bookmark using the normal native token recipe and closes that page.
The new process has its own native input instance and page root. Its original
source basis still points to the unchanged startup file; later file/model
observations establish deletion independently. Ignored native tab input retains
that responsibility and a reconstructed owner sends no second delete attempt.
The new sources are explicit models; these two tests establish no device result.

The current-stage coordinator now delivers the final ordinary Go To through
`NavigationProcessReturn`. Its durable child journal resolves only a fully
retained lost return; an unknown delivery is not resent. Three connected host
tests cover actual loopback static-scene import bytes, ignored Go To and lost
final owner writes. Delivery claims neither restoration nor destruction of the
hidden address QML root. Eight existing return tests also pass after preventing
their modeled host clock from regressing behind an earlier fixture reply.
Native timestamps and production freshness checks remain unchanged. Initial
static PNG ownership, full restored originals and paired final retirement still
gate complete Worlds capability admission.

`NavigationBaselineImage` now owns a distinct untouched static PNG per role.
The existing candidate-qualified runtime supplies actual native clocks, all
eight source readers and the original Vulkan frame owner. Each passive query
is reserved before delivery; raw components remain immutable private files with
exact hashes instead of enlarging packed-metadata limits. The complete native
bracket joins the independently observed static import/map, settled original
pose and recorded Vulkan view to unmodified PNG pixels and actual GPU release.
Historical replay sends no source or SDK command and cannot renew freshness.
A later run scene, blank image, changed component/candidate, partial source,
lost final write or lost GPU read cannot become a fresh untouched baseline.
Seventeen host tests cover this owner and the runtime factories. Native code
remains uncompiled and devices untested. Whole preparation must still retain
both role baselines before entry and acquire a new actual admission cut just
before its first ordinary input; this image owner alone grants no capability.

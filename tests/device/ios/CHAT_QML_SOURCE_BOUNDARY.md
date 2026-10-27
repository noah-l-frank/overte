# Actual Chat QML load boundary

Feature 10 remains partial. Submitted Chat JavaScript bytes and a live Chat
page are independently observed; neither currently supplies the missing
consumed/compiled QML-byte association. No additional capability is admitted.

## Inspected production path

The original [Armored Chat script](../../../scripts/communityScripts/armored-chat/armored_chat.js)
resolves `./armored_chat.qml` and calls the existing Tablet loader. The actual
[TabletProxy](../../../libraries/ui/src/ui/TabletScriptingInterface.cpp)
`loadQMLSourceImpl` invokes the root's `loadSource` method. The existing
[TabletRoot](../../../interface/resources/qml/hifi/tablet/TabletRoot.qml)
then calls `QmlSurface.load`, retaining the actual load ticket and created item.

[OffscreenSurface](../../../libraries/qml/src/qml/OffscreenSurface.cpp)
`loadInternal` resolves the URL, applies the actual iOS override selection and
constructs `QQmlComponent` from that URL. `finishQmlLoad` receives the component,
context and actual new object, calls `beginCreate`/`completeCreate`, observes
errors and eventually deletes the component. Callback ordering depends on the
existing `completeBeforeCallback` path. No observer may equate an earlier
callback with successful final completion.

The current [native Chat controls](../native/NormalChatControls.h) hash the
actual context's **source location** into `componentSourceSha256`. Its existing
[contract](../native/NORMAL_CHAT_CONTROLS.md) explicitly distinguishes that value
from installed executable/QML-byte association. The existing submitted Script
source receipt does not close this separate boundary.

The [development revision selector](../../../ios/development/DevelopmentOverrides.h)
checks its manifest and selects roots at startup. Its
[QML URL interceptor](../../../ios/development/QmlOverrideInterceptor.h)
can redirect resources into those roots, with missing resources falling back
to bundled ones. The older Documents override path also exists in
`OffscreenSurface`. A requested logical resource URL alone cannot identify the
actual consumed bytes. Revision selection is not UI execution evidence.

## Missing observation and next executable step

The current loader supplies no retained receipt of the source/compiled unit
actually consumed by that `QQmlComponent`, tied to the actual created Chat
root and context. Reading a current QFile separately, hashing the URL, choosing
an expected pin or replaying the JavaScript loader cannot supply this fact.

The repository's [toolchain pin](../../../ios/versions.env) is Qt 6.11.1. This
is configuration, not evidence of the installed client's Qt version. The next
source task is to inspect the matching verified Qt source/package's actual
component/compiled-unit API and identify a passive consumption receipt. It
must bind the real resolved source and compiled/source bytes to the exact
component, final completion result, context, root object, process and native
clock, retaining weak lifetime and original sequence responsibility. Imports
and overrides must remain explicit. The actual installed candidate and matching
Qt provenance must independently admit it before ordinary input.

This packet deliberately introduces no guessed private Qt API, alternate
loader, forced cache clear, `setData` replacement, new source query or asserted
loaded-byte field. Product loading behavior is unchanged. Native implementation,
host counterexamples and canonical Chat integration of that receipt remain
required; no compiler, build, SDK installation or device access was attempted.

## Verified Qt source reference

Read-only inspection of the official Qt Declarative `v6.11.1` source supplies
the concrete private interfaces for the next implementation:

- [QQmlComponentPrivate](https://raw.githubusercontent.com/qt/qtdeclarative/v6.11.1/src/qml/qml/qqmlcomponent_p.h)
  exposes its actual executable compilation unit;
- [QQmlData](https://raw.githubusercontent.com/qt/qtdeclarative/v6.11.1/src/qml/qml/qqmldata_p.h)
  separately retains the created object's compilation unit;
- [ExecutableCompilationUnit](https://raw.githubusercontent.com/qt/qtdeclarative/v6.11.1/src/qml/jsruntime/qv4executablecompilationunit_p.h)
  exposes actual compiled-unit data;
- [QQmlTypeData](https://raw.githubusercontent.com/qt/qtdeclarative/v6.11.1/src/qml/qml/qqmltypedata.cpp)
  passes the actual source string to the QML IR compiler. Its disk-cache branch
  can bypass that call, and its completion cleanup discards the temporary source.

These are reviewed source interfaces, not an installed private ABI or a native
runtime result. The six exact reference files, original URLs, byte counts and
SHA-256 hashes are retained privately under
`.ios-host-tmp/qt-qml-readonly-6.11.1-9es8y5lo`, with two status manifests.
Only small source files were read; no Qt archive, dependency or SDK was installed.

The next native packet should observe the actual compiler input and completed
unit together, then bind that receipt to the actual component/root unit at the
existing final-completion point. It must remain behind the dedicated iOS E2E
configuration and preserve ordinary compiler/loader results. A source read
after completion cannot replace the input tap. An opaque disk/AOT cache hit
without independently retained source association must remain unavailable;
neither clearing caches nor treating the observed digest as its own expected
pin is acceptable. Imported units and native AOT dependencies need their own
explicit admission. No such receipt or Qt source patch is implemented yet.

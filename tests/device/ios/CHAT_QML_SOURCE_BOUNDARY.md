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
is configuration, not evidence of the installed client's Qt version. The
source review below identifies the matching component/compiled-unit API. The
remaining native client task must expose a passive consumption receipt. It
must bind the real resolved source and compiled/source bytes to the exact
component, final completion result, context, root object, process and native
clock, retaining weak lifetime and original sequence responsibility. Imports
and overrides must remain explicit. The actual installed candidate and matching
Qt provenance must independently admit it before ordinary input.

The source-only Qt patch below introduces no alternate loader, forced cache
clear, `setData` replacement or client source query. It is not applied to an
SDK or wired into the client. Native compilation, client observation/transport,
cache-provenance coverage and canonical Chat integration remain required; no
compiler, build, SDK installation or device access was attempted.

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
runtime result. The eight exact reference files, original URLs, byte counts and
SHA-256 hashes are retained privately under
`.ios-host-tmp/qt-qml-readonly-6.11.1-9es8y5lo`, with four status manifests.
Only small source files were read; no Qt archive, dependency or SDK was installed.

The next native packet should observe the actual compiler input and completed
unit together, then bind that receipt to the actual component/root unit at the
existing final-completion point. It must remain behind the dedicated iOS E2E
configuration and preserve ordinary compiler/loader results. A source read
after completion cannot replace the input tap. An opaque disk/AOT cache hit
without independently retained source association must remain unavailable;
neither clearing caches nor treating the observed digest as its own expected
pin is acceptable. Imported units and native AOT dependencies need their own
explicit admission. The first direct-unit source patch is now present as
described below; none of its native/runtime behavior is qualified yet.

## Unapplied direct-unit source patch

The [exact Qt 6.11.1 patch](../../../ios/patches/qtdeclarative-overte-e2e-qml-source-receipts.patch)
records the actual decoded QString immediately before the existing IR compiler.
It hashes exact little-endian UTF-16 code units and their measured count;
it does not call those values original QFile/network bytes. The successful
direct compiler unit must retain both its managed owner and its actual data
identity through completion, with unchanged bounded unit bytes. Metadata is
owned by that actual Qt CompilationUnit, not a global URL/pointer table.

The patch retains Qt's ordinary compiler and cache calls. In particular,
`compile()` can save and reload its output. **Every attempted post-save cache
reload clears the direct input receipt**, even when the final compiled digest
is equal or the reload fails. Different inputs can compile to equivalent data;
equality cannot prove which input produced a substituted cache generation.
Opaque disk/AOT units remain unavailable. A causal cache write/read bridge
is still required for that normal path; this packet does not substitute a
smaller successful profile for complete loaded-QML coverage.

Every actual `setUnitData`, cache-load attempt and destructor invalidates the
unit's receipt centrally. A bounded mutation generation also fences a pending
publication; restoring equal bytes or reusing an address cannot restore its
old input association. The getter checks the retained generation again.
Inspection of the reviewed implementation found its live data replacement in
the central setter and its final direct null assignment in the destructor;
both are covered by this source patch.

Exported API-version, enable and object-receipt functions are defined inside
the patched Qt binary. The object reader checks the actual QObject's unit,
optionally its exact component unit, the owning thread, native process and
current immutable unit bytes. Client integration must call these binary APIs,
not access newly added private fields using only a header marker. A matching
dedicated E2E Qt package and independent binary/source admission are required;
existing Qt cache/toolchain identities cannot be reused as proof of this ABI.
The added private wrapper fields change its memory layout: every affected Qt
private consumer in that dedicated SDK must use the same patched headers and
be rebuilt together. Replacing only the QtQml library in an old SDK is outside
this design. The persistent QML Unit/cache format itself remains unchanged.

The observer is initially disabled and requires explicit native enable plus
`--testScript`; its additions compile only for iOS. Future client activation
must also use the existing dedicated feature-test configuration. Errors in
diagnostics do not replace the ordinary compiler input/result. Qt's inspected
[completion dispatch](https://raw.githubusercontent.com/qt/qtdeclarative/v6.11.1/src/qml/qml/qqmldatablob.cpp)
invokes `done()` before publishing Complete and dispatching ready callbacks;
the source patch publishes metadata inside that completion scope. No source
patch was applied to the workstation Qt, a build cache or another checkout.

The [offline verifier](verify_qt_qml_source_patch.py) verifies all eight exact
source-reference hashes from the [manifest](qt-qml-source-patch.json), applies
the five-file patch only to a new private copy, checks reverse application and
rechecks every original file's identity/bytes. It never compiles or installs:

```sh
python3 tests/device/ios/verify_qt_qml_source_patch.py \
  --source-root /path/to/reviewed/qt-everywhere-src-6.11.1 \
  --scratch-parent .ios-host-tmp
```

Three host cases exercise actual private application, foreign-source rejection
before mutation and refusal of an external scratch directory. Runtime API,
compilation and device flags in the actual verification report remain false.
These checks establish source-patch integrity, not native correctness, loaded
client execution, the still-missing cache bridge or a complete Chat capability.
The final central-invalidation selection passes **3 tests in 0.017 seconds**;
log: `.ios-host-tmp/qt-qml-source-patch-central-invalidation3.log`. Prior three-case
passes belong to the earlier source revisions and are not additional cases.
The final reference layout is `qt-qml-reference-layout8-oi578q5j` beneath that
private directory. All eight original references retain their exact identities
and bytes. The scope does not execute Qt, native code, a compiler or a device.

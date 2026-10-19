# iOS original Create controls v1

`IOSAdapter._create_controls(selector, intent)` composes the common
`TokenCreateUI` with `create_controls.IOSCreateIO` on the existing normal Script
component's real foreground PID/session/fingerprint continuity closure. This is
`NATIVE_UI_COMPONENT_ONLY`; it neither binds an installed IPA's bytes nor enables
any `feature.create.*` capability. The canonical candidate adapter explicitly
refuses this factory with `OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE` before I/O.

`IOSNormalUiInput` uses the shared actual `NativeCreate.qml` identities and
metadata. The observation adds `createControlsVersion:1` and `createGeneration`,
which is the original normal-root generation already rotated when the HUD,
tablet or tablet visibility changes. It is available without an AccountManager
result. Original frames are validated by the existing native reader, then only
Create/navigation rows are projected into the common contract. Original values
and geometry participate in source tokens; unavailable page/selection/text is
an error, never a fabricated empty value.

All recipe input uses the existing closed HTTP/private-AFC `normal-ui-input`
transport. The normal input `edit` request can now carry `operation:activate`
with an original field token and instance/consumed-sequence/elapsed reference.
It has no control ID, coordinates, expected state or entity payload. Native
admission restricts activation to actual Create and tablet Home/page items;
non-Create activation is refused. The normal Qt pointer path and focused field
IME/key path share the existing consumed-input sequence. Scrollbar clicks use
actual thumb geometry and ComboBox choices use actual focused Home/Down/Return.
No property setter, QML handler, Create bridge or Entity service is an input.
Create gets no duplicate UIKit accessibility widgets from this instrumentation.

`NativeInput.create_input` retains the caller's original reference through a
fresh native admission read. Context/PID/generation/sequence/row must match and
the original elapsed reference must remain within five seconds; the backend
cannot adopt a newer selection/token or reset its age. Native sequence intent
is consumed before uncertain event dispatch. The mandatory callback must persist
private ownership before every input. The enclosing coordinator still has to
own and clean its panels/entities/files and independently judge entity effects;
the helper does not perform that composition or clean up someone else's panel.

Six synthetic-boundary cases exercise the actual fixture grammar, HTTP/AFC
reader and normal-input Python code. They cover ignored choice/text/scroll,
changed selection before and during dispatch, missing source/version/frame,
failed journal intent, lost PID and canonical installed-code refusal. The
complete permitted iOS host selection passes **306** tests with no skips/errors/
failures/compiler attempts; the 20 existing native/compiler-dependent checks
remain explicitly outside the no-build scope. Five canonical entry/binding
checks pass separately. Discovery initially exposed shared/platform import-name
collisions; shared fixtures now use their namespace and this adapter deliberately
uses `create_controls.py` to preserve the legacy utility-path import behavior.

Native C++/ObjC++ is uncompiled. Ordinary focus/popup/scroll/layout and the full
product run remain unqualified on iOS. The model/texture, JSON picker/export,
PolyVox, permission actors and original file/image/peer joins required by the
complete Create v8 journey are still missing. The source contract is documented
in [`NORMAL_CREATE_CONTROLS.md`](../../native/NORMAL_CREATE_CONTROLS.md).

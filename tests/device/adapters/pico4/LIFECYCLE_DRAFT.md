# Normal original Create draft controls

`native-lifecycle-controls:1` adds one source-qualified normal control:
`lifecycle.create.text`, the actual `NativeCreateText` / `newText` field on
Create's initial tab. The expected full QML URL is obtained from native
`PathUtils::defaultScriptsLocation()`, matching the passive Lifecycle source.
A similarly named field or matching source-path suffix cannot qualify.

The existing `NormalControlUi` has a narrow Lifecycle surface, and the actual
Pico normal navigation bridge publishes the same metadata and consumes the
same original normal pointer / `NativeFieldInput` routes. Normal Create entry
and tab navigation remain the existing normal Create controls. No Text entity
button, Submit, QML handler invocation or entity mutation is exposed here.
All additions require the dedicated feature build and `--testScript` runtime
path; installed candidate, process, original bridge, foreground and private
normal-file admission remain the existing Pico adapter's checks.

Each native field row includes the actual text/focus/readiness, canonical
source URL hash, and weak original field/page/QQmlContext/window identities.
Those identities never reuse a dead object's token. The normal control token
also binds that original source state, text, focus and visible geometry. A
page or context replacement cannot inherit a captured input token. This is a
separate normal-control identity namespace; passive Lifecycle editor IDs are
not asserted equal to these IDs. Whole-journey joining must use the actual
original root/source binding and preserve both original observations.

`pico-lifecycle-draft-controls:1` provides the strict projected reader and
`TokenLifecycleUI`; `_lifecycle_draft_controls(target, intent, run)` binds it to
the actual existing Pico normal bridge. A caller-supplied durable intent must
precede input; a failed or slow intent cannot send. The reader accepts only an
empty field and the closed current run's Unicode draft. It focuses via normal
pointer input and replaces via the original native IME helper. Native input
cursor advancement is input consumption only: focus and actual text must then
be observed afresh on the same original objects. Ignored input, another run's
draft, a changed native reference, source/component, PID or generation fails.
Uncertain input is never retried by this primitive. The complete journey must
own its durable input journal before using it and reconcile original effects;
this component does not invent a recovery or clear someone else's draft.

The focused Qt check compiles the actual `NormalControlUi`, new source helper
and complete original `NativeFieldInput.cpp`, then loads the original
`NativeCreate.qml`. Assertions execute actual native pointer/IME Unicode
input, independent original Qt text reads, unchanged entity-request signal
count, stale token rejection, original weak object replacement, and runtime
gate refusal. Native PathUtils configuration and the host Qt window/pointer
endpoint are declared test boundaries. This is not a VR controller/keyboard or
whole Pico client run. The Pico bridge additions are source wiring; the focused
compiler does not compile that complete application translation unit.

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=<private-directory> \
  OVERTE_NATIVE_QT_MAJOR=5 OVERTE_QT5_HOST_ROOT=<reviewed-qt5-root> \
  python3 tests/device/contracts/tablet/test_lifecycle_controls.py
PYTHONDONTWRITEBYTECODE=1 TMPDIR=<private-directory> \
  python3 android/vr/pico/tests/pico4-test-suite.py --test lifecycle-input-owner
```

The existing Lifecycle catalog group is extended; no new group or complete
`feature.lifecycle-input.*` capability is advertised. The separate
[durable editor owner](LIFECYCLE_EDITOR.md) now composes normal opening, focus,
Unicode, first blocked world consumption and X. Pending/stale and background
composition, later editor generations, peer/image evidence, restored original
position and resource closure remain separate unfinished journey work.

# Phone adapter implementation, local source only

Branch: `test/android-phone/shared-feature-adapters-20261019`.
Product base: `718d069add` (Phone typed-config parity repair), composed with the
Main common-journey branch through ordinary local parent-to-child merges.
No protected integration, build, install or device execution was performed.

New implementations in the existing candidate-bound Appium entrypoint:

| Operations | Source implementation | Product/device evidence |
| --- | --- | --- |
| `scripts.manager.open/close`, `scripts.load-url`, `scripts.restart/stop` | Normal Tablet/From URL/row input; actual native URL identity; persistent cleanup intent | Host boundary tests only |
| `create.reference.open/close`, `create.cube/update/undo/redo/delete/import` | Normal Create controls, original read-only observer, actual avatar entity IDs and cleanup | Host boundary tests only |
| Existing `places.*`, `snapshot.*` | Existing Phone native navigation and original SNAP-file implementation retained | No new device qualification |
| All `feature.<area>.act/observe/cleanup` | **Not implemented as complete v1 area adapters** | Never advertised; required capability gates remain red |

For a later Proxmox laboratory candidate only, opt in separately with
`OVERTE_PHONE_NORMAL_SCRIPTS=1` and/or `OVERTE_PHONE_NORMAL_CREATE=1` in the
private execution environment. The original candidate arguments, installed-APK
hash binding, controlled app-private command/probe configuration and explicit
target remain mandatory. No private target files were changed. An invalid opt-in
or an unbound/wrong product is rejected. The new probe producer must be present
in the actual later APK; enabling flags against an old candidate fails before
feature input. The adapter never installs or builds a replacement implicitly.

The read-only command is correlated to a fresh random request ID. It returns
original service/entity reads once, with a source sequence and actual capture
time; no recurring entity-query overhead is added to unrelated test suites.
The adapter checks PID+start ticks, foreground, original Appium session and
generation, target fingerprint and actual installed bytes around operations.

Implementation details and exact bounds are in
[normal scripts](../NORMAL_SCRIPT_MANAGER.md) and [normal Create](../NORMAL_CREATE.md).
Phone-owned UI bindings are `overte_phone_script_ui.py` and
`overte_phone_create_ui.py`; Main owns only the reusable flow/observation code.
No primary action uses a direct entity/script service mutation. UI ACKs remain
input receipts; the existing shared journeys independently inspect real effects.
Create Name/Color/Dimensions edits use actual W3C keyboard actions (Select All,
ordinary ASCII keys, modifier release and native field readback), because
`NativeCreate.qml` accumulates changes on Qt `textEdited`. Accessibility set-value
alone would not establish those edit events. Actual UiAutomator2/Qt key delivery
and off-screen field reachability still require later physical qualification.

Cleanup first tries normal owned entity/source cleanup, then the original
adapter-wide app/session teardown. If candidate/process continuity is lost, an
ignored deletion/stop remains, or an import has unresolved native completion,
cleanup fails and retains ownership state. A stopped process alone does not
establish removal of persisted avatar entities or saved Running Scripts.

The full fourteen-area v1 adapter is concretely blocked by missing complete
product observers, native lifecycle counters, original world-render target
capture, external real peer/account/domain fixtures, and delivery of original
record/share/upload bytes. See the common fourteen-area audit. In particular,
the source-reviewed From URL action loads directly, without the consent
cancel/reject flow required by the full scripts feature scenario; this must not
be disguised by a synthetic dialog in the adapter.

Hardware-free checks (run from this worktree):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s android/phone/tests/device -p test_feature_adapters.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s android/phone/tests/device -p test_installed_identity.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/device/self_tests -p 'test_normal*py'
```

The first test is also registered in `phone-e2e-runtime-regressions.py`'s existing
mandatory `COMMON_HOST_CHECKS`; no new CI workflow was introduced. These tests
substitute only native W3C/ADB/time boundaries and synthetic candidate bytes.
They prove control logic and failure handling, never Overte feature success or
Phone acceptance. All physical qualification remains pending on Proxmox.

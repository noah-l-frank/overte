# Original normal SNAP capture controls

The existing normal-input transport has an optional closed capture-control
extension, version 1. Capture/name/mode/format/cancel rows retain their original
identifiers and gain the actual selected QML root UUID/source, current mode and
format, image count, pending/processing/settings/error state, and UIKit blocking
state. The title is observed as a SHA-256; only a controlled run-prefix title is
also exposed in clear text. Foreign drafts remain redacted and cannot be edited.

The QML properties are passive, readonly bindings, disabled without the actual
dedicated feature API and `--testScript`. No handler, capture setting or export
slot is changed. Native source-token identity includes these original fields.
Native code rechecks current ownership, the actual point and UIKit presentation
before sending ordinary Qt mouse/key input. It retains a copy of a control ID
across map refresh, rather than a reference invalidated by that refresh.

The new Python `snapshot_capture_input` route supports ordinary activation and
focused name replacement. Replacing a name requires its original actual empty
or controlled name hash. An owned controlled title can therefore be restored to
the actual original empty title using ordinary key events. The legacy general
`edit` API keeps its existing nonempty controlled-prefix requirement. Both APIs
still require the outer durable input owner; an ACK establishes no capture,
timely cancellation, file, image or clean resource lifetime.

Original capture controls in one observation must agree on the actual root and
all shared settings/state. A changed title/mode/format/root, stale source token,
missing source extension, foreign draft or native system sheet refuses input.
Mode/format menu options retain their existing ordinary menu-input path; this
extension does not add a direct setting setter or a normalized capture verdict.

Eight no-build host cases cover the real Python normal-input transport over
modeled Qt/UIKit facts, actual empty-title restoration, mixed roots, source
replacement and blocked/foreign input. Together with the existing export/input
and production JavaScript source semantics, 22 Python cases pass; the latter
executes all thirteen actual production JavaScript cases. Native C++/QML remain
uncompiled and devices remain untested.

Whole Snapshot input journaling still must join these original controls to
[actual Script/timer work](SNAPSHOT_WORK.md), [native capture lifetimes](SNAPSHOT_CAPTURE_LIFETIMES.md)
and independent original file/image evidence, then drive restoration and paired
cleanup. This component enables no complete Snapshot capability.

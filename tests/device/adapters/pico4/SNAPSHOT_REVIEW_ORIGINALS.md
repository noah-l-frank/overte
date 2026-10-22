# Passive original Snapshot Review on the Pico tablet

The existing `NavigationUi::observe` now publishes `picoSnapshotReview` from
the actual supplied Pico tablet root and its same original QQuickWindow. This
is an additive private E2E source; normal controls, input sequences, tokens,
mode/format choices and public Snapshot operations are unchanged. It does not
advertise a complete Snapshot capability or provide input/export authority.

`SnapshotReviewObservation.h` selects the passive observer from fixed Phone
`5527d540e99cc6dba4204a5e904a854e6e1cd2b4`, retaining its original QML-context
qualification, bounded tree traversal and property checks. It removes the
Phone-only compilation guard for this neutral Qt component and supplies an
explicit Pico root/window association wrapper. `OVERTE_E2E_FEATURE_TESTS`,
actual `--testScript`, the original GUI thread, current root/window association
and actual native publication site remain required. There is no Phone window,
Phone touch driver, handler invocation, setter, timer or service initialization
in the source. The existing publisher owns private process/candidate transport.

The exact version-2 source distinguishes (archived version 1 remains readable):

- A valid live original root with no Review: `present=false, review=null`.
- A real Review qualified by its original `root` QML ID, context base URL and
  `sendToScript(QVariant)` signal: `present=true`, even while hidden.
- Missing/detached root window, foreign same-name page, ambiguous pages or
  malformed original properties: unavailable; no source field is published.

It reads original capturing/processing/settings, visibility, current mode and
format, the actual `captureName` TextField text, image-row paths/story presence and platform export properties from
that page. The Python source parser and existing Pico navigation parser retain
closed keys/types and explicit bounds. They do not infer an effect from an
input receipt or an expected value. A detached old page can still live outside
the current visual root; an observed absence is never Qt/context retirement.

Version 2 requires the original bounded name field qualified by its real QML ID
and object name. Version 1 has no name fact and cannot establish a run-owned
capture filename. An old source cannot be silently upgraded by a requested name
or an input receipt. The compiler check types the owned name through the whole
original `NativeFieldInput.cpp` and actual Qt input-method events before reading
it independently from the page.

The owning `snapshot-review-originals` selector has four strict parser/root
boundary cases plus one actual native QML check. The latter compiles the
selected whole source header with real Qt5/6-compatible APIs, loads the
unchanged production `NativeSnapshotReview.qml` on a real host QQuickWindow,
drives its actual Capture button by pointer, and observes the original QML
properties and hidden page. Duplicate and foreign contexts, wrong window,
missing root and retained detached page are explicit counterexamples. It also
runs without `--testScript`, when the source remains unavailable. The output
from the actual C++ source is decoded by the strict Python validator.

Snapshot native services, keyboard service and Android export backend are
explicit host boundaries in that compiler check. Synthetic `fromScript`
delivery tests the passive property source and is never labeled as a real
capture/cancel/VM effect. This does not compile the whole NavigationUi unit,
run an APK/device, prove real VR hit testing or qualify Android export.

The next normal vertical step is the fixed original FastCancel recipe, bound
to this Review, the [VM source](SNAPSHOT_SCRIPT_ORIGINALS.md), accepted native
request history and existing Pico normal control route. The ordinary Capture/
Cancel route, independently pinned actual Script compilation and fresh phase/
process ownership must all join before the required pre-render cancellation
is qualified. No second timer/cancel system or weakened v16 cleanup is supplied.
All existing Snapshot journals and files remain owned.

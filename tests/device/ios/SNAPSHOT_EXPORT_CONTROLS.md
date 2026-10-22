# Original normal SNAP export controls

The existing iOS normal-input transport now observes the real Save, System
share and Upload buttons for each of the eight bounded SNAP image rows, plus
Cancel export/upload. Existing capture/name/mode/format controls keep their
original grammar. The new optional native control extension and projected
control group have their own version 1; old normal-input originals remain
readable and cannot invent this extension.

`NativeSnapshotReview.qml` exposes the added row/button identities only when
the dedicated native iOS feature API is present and `--testScript` is active.
The original handlers and their arguments are unchanged. Observation identifies
the actual QML root/context, its own UUID birth, actual row index, controlled
filename, current export ticket, capture/processing state and real enabled/
hit-test readiness. Foreign filenames are redacted and cannot qualify normal
export input. These values are input targeting metadata, never Save/delivery
outcomes or installed-code admission. Canonical candidate binding and the
separate source/file originals remain required.

New metadata participates in the existing original source-token identity.
Native code rechecks that identity and actual point ownership before sending
the normal Qt mouse press/release to the current target. It invokes no export
or capture slot directly. The Python route preserves the token, original native
elapsed time and next input sequence; a changed root, row, filename, ticket,
frame, process, sequence or old reference prevents input before delivery.
The outer input owner must durably retain this normal-input responsibility;
an acknowledgment alone is not a product effect and never authorizes resend.

Actual UIKit presentation and application-active state also gate readiness.
An authorization alert, activity controller or native picker must receive real
system input; this route refuses a Qt click beneath its presented controller.
It does not dismiss a sheet, grant permission or infer saved bytes. System
permission/share recipes remain a separate required integration boundary.

Five no-build checks compose the real Python transport and validators over
modeled Qt/UIKit observations, including source replacement, blocked sheets,
legacy packets, strict versions, old references and foreign transport nonces.
The eight existing normal-input tests also pass. Native C++/Objective-C++ and
the QML extension are uncompiled; no device or installation is accessed. This
component does not advertise a complete Snapshot capability. See the separate
[native export](SNAPSHOT_EXPORTS.md), [capture lifetime](SNAPSHOT_CAPTURE_LIFETIMES.md)
and [Script/timer](SNAPSHOT_WORK.md) original sources.

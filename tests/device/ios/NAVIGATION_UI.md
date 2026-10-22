# Original iOS Go To visibility inventory

The optional `navigationInventory` extension of the original normal-input
snapshot carries `iosNavigationUiInventoryVersion: 1`, a complete flag and actual
retained Go To roots. Existing snapshots without the extension remain readable;
the Worlds projection requires it. No complete capability is added.

The iOS source uses the existing bounded passive whole-tree walk, before input
hit testing and modal suppression. It identifies the selected original
`+android_phoneInterface/AddressBarDialog.qml` root through its original QML
context, and reads its actual `shown`, effective Qt visibility, window presence,
and original address field text, visibility and focus. It assigns a weak native
object UUID; retained QPointers keep detached roots observable until actual
destruction. A hidden object remains distinct from a destroyed object. An
unselected/foreign field, traversal limit, missing original field or incomplete
tree yields incomplete evidence. Nothing opens, closes or edits a dialog.

This addition is gated by `OVERTE_E2E_FEATURE_TESTS` and iOS, and its complete
observation additionally requires `--testScript`. Release behavior and existing
input routing are unchanged. Existing native snapshot PID, source instance,
input sequence, native UTC and elapsed clocks retain their original meaning.

`navigation_ui.project` requires the complete original extension. A covered or
clipped input target may disappear from the normal control list while its real
dialog stays visible. This projection reads the actual root instead. A shown
detached object or multiple visible roots is uncertain and cannot establish
closure. Historical projection leaves the original timestamp unchanged; a live
consumer must separately join the original snapshot to a bounded native clock
acquisition and installed-process binding.

This is a visibility prerequisite, not dialog/callback destruction, keyboard
drainage, a quiet window or whole-journey cleanup. Host tests exercise the actual
Python validator and original normal-input HTTP/AFC transport with Qt, process
and AFC ports modeled. They cover covered controls, retained hidden roots,
incomplete inventories, source/identity errors and stale/foreign envelopes.
Native code remains uncompiled and devices untested.

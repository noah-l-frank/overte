# Ordinary Go To retained-root ownership

The selected `+android_phoneInterface/AddressBarDialog.qml::closeDialog` calls
`DialogsManager.hideAddressBar`. On iOS that reaches `OffscreenUi::hide`, which
writes the existing root's `shown` property to false. It does not delete the
QML object. The passive native inventory correctly retains such hidden roots
through weak identity tracking. A disappeared input control is not destruction.

`navigation_address_roots.py` is a pure version-1 ownership validator. The
enclosing ordinary input owner must retain its actual HUD lookup result and
durably record the matching click intent before delivery. The validator binds
that actual SDK element reference to the original normal Go To locator, a
root-free original native UI packet and a later original visible selected QML
root. A click acknowledgment alone supplies no root. A preexisting hidden root,
another component, ambiguous roots, changed process or reused source counter
cannot be adopted.

Subsequent original packets must retain the actual root ID/component and native
source/input history. A hidden, unfocused root is reported as `retained`, with
`drained=false`; its original text is preserved as data. Only a complete current
native inventory with no root and no address control reports `absent`. The
validator neither hides nor destroys any object, and it makes no statement
about unrelated callbacks or whole-run cleanup.

This is a prerequisite for the normal scene/missing-input owners to journal
their actual opening originals and transfer the retained root through restart.
Those input hooks and whole cleanup are still required. The existing process
context remains conservative and refuses retained roots until that explicit
handoff is connected. No feature capability or whole-area completion is enabled.

Thirteen explicit host tests cover root UI inventory and this ownership join,
including hidden versus absent, incomplete inventory, foreign SDK lookup,
preexisting/replaced roots, focused hidden fields, source rollback and historical
tampering. Qt/SDK boundaries are modeled; native compilation and devices remain
unverified.

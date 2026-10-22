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

`NavigationAddressInputs` writes version 2 and reads versions 1 and 2. It wraps the existing `IOSNavigation`
ordinary recipe for scene entry and original-scene return. Its separate
process-qualified private journal retains the actual HUD lookup, each matching
UIKit click intent, focused Qt field original, exact native command UUID and
original transport receipt before advancing. Every mutation is recorded before
delivery and checked against both host freshness deadlines after journaling. The
selected original QML root is retained across both recipes. Returning to a
hidden root with foreign text is refused before reopening.

Lost HUD, native-edit and completion responses remain issued and are never
resent. `observe_pending` may make a distinct passive read to retain the actual
root after an uncertain opening; it cannot acknowledge or resume the recipe.
Repeated acknowledged calls return their saved input result without issuing a
new command. The original scene-input version-1 carrier stays readable. Older
acknowledgments without the new root journal do not authorize adoption of a
preexisting root.

The version-2 process context now accepts this original closed ownership only
alongside independent old-process death and new-process root absence. The
ordinary restart controller and whole cleanup still require integration. No feature capability or whole-area completion is
enabled.

Thirteen explicit host tests cover root UI inventory and this ownership join,
including hidden versus absent, incomplete inventory, foreign SDK lookup,
preexisting/replaced roots, focused hidden fields, source rollback and historical
tampering. Qt/SDK boundaries are modeled; native compilation and devices remain
unverified.

Seven additional host tests exercise the real ordinary Python recipe, private
journal, HTTP dispatch and AFC receipt boundary with modeled native UI. They
cover the retained root across entry/return, original nested command nonces,
lost mutation/completion returns, read-only pending-root acquisition, preexisting
objects, foreign retained text, ignored edits and Go To, expired input intent,
changed candidate and original-root tampering. Ten existing scene-entry/return
tests now model the actual retained root rather than silently dropping it.

The version-2 missing-destination input owner now delegates its exact hidden run
name to this same retained-root journal. This remains a separately closed recipe;
the normal public Places operation still accepts only controlled viewpoints.
The actual original Qt command/receipt and root carrier are retained inside the
missing-action journal before its delivery result is acknowledged. Entry,
missing-name lookup and original-scene return share their actual root when they
occur in the same process. An uncertain Go return stays issued in both owners;
a separate passive acquisition may retain the hidden root without replay.
Version-1 address and missing-action carriers remain readable in their original
shape and cannot supply the new root handoff. The original 404/OK/listener-death
proof remains independent of input delivery and hidden address controls.

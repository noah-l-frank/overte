# Retained Avatar and People QML roots

The optional closed `avatarInventory` component of the unchanged normal input
observation retains actual AvatarApp/Pal root identities and all four Avatar
dialog visibility properties or the People connection prompt. Its passive
survey precedes input hit-testing. Native `QPointer` entries keep roots which
were observed during that survey visible to subsequent getters after hiding
or visual detachment, until actual QObject destruction.

The component writes/reads `ios-avatar-ui-inventory` version 1. Existing
Controls1 records without the optional component remain readable. Full cleanup
requires the component, complete traversal and an empty retained-root list;
visible input rows alone never establish absence.

This getter remembers roots it actually encountered. It is not a global QObject
creation ledger and cannot establish the absence of an arbitrary transient
root that was never observed. Whole-feature cleanup must retain positive
original root admissions associated with its ordinary inputs, or separately
prove actual process death/another original closure for an unknown opening.
Root/dialog absence also does not establish JavaScript callback or timer drain.

Host tests exercise the real Python normal HTTP/AFC read path and original
receipt. A synthetic Qt boundary uses real host weak references to keep hidden,
detached roots alive until actual weak expiry. Legacy, incomplete, malformed,
duplicated and foreign-source packets fail closed. Native source ordering and
gates are inspected; native compilation and device behavior remain untested.

# Original ordinary Tablet app button ownership

`IOSTabletAppButtonsObservation.h` and `tablet_web_buttons.py` expose distinct
actual model insertion, native API return, clicked signal, model erasure,
proxy weak expiry and bound QML control weak expiry. Source version 1 and the
separate `tabletAppControlsVersion:1` normal-input extension are prerequisites;
they do not qualify the complete Tablet Web feature. Native code is uncompiled
and no device has executed it in this session.

The actual ScriptManager native-call scope captures `addButton` caller membership
and evaluated code before the ordinary VM-to-native method invocation. Its
immutable original crosses the existing blocking Qt thread boundary only under
the actual E2E flags. The ordinary inactive invocation remains unchanged. After
actual model insertion the source reads the real returned proxy's UUID and
properties. After the actual TabletProxy call returns its proxy, the observer
associates the genuine Tablet/root. These events never synthesize a click or a
Web navigation. The passive clicked-signal listener records only its actual
signal entry; Script signal callbacks, VM work and worker termination remain
separate original obligations.

Only the closed ordinary fixture app's semantic run/generation/verb and actual
`fixtureUrl` property select rows. The caller is retained as an original, not
adopted from labels. The Python `selected` join requires the independently owned
Script membership/code and the actual live returned proxy/control. Controlled
input properties never replace a measured browser address, successful load,
DOM content, bridge result or image.

Model removal captures an immutable row ID before erasing the actual shared
proxy. It does not dereference the raw pointer after erase and does not assume
erasure destroyed it. Persistent source pointers are QPointers. A held proxy
or QML delegate remains alive until a later original zeroing-weak observation.
Shared TabletProxy/model objects are not owned by this fixture app and are not
required to die with it. Logical native caller and clicked originals never reset.

The actual QML root can be observed when the real app controls are created,
before the first Web navigation. The Sources1 helper reuses that same weak root
birth for later ordinary navigation; its existing query grammar and fixture
filter remain unchanged. Root registration supplies no navigation or source
fixture by itself. A control must have the actual proxy UUID, semantic property,
returned source row, signal and visual ancestry under that original root.

The existing normal input collector exposes only its three source-qualified
controls. Its original token covers the complete actual source JSON. Final
input dispatch rechecks the same source and normal hit test before the existing
ordinary Qt mouse press/release. UIKit creates the existing source-token button,
and UIKitInput2 separately retains its real weak native association. An input
ACK or clicked signal is never a Web effect or a cleanup verdict.

Five host tests distinguish actual retained weak proxy and visual objects,
refuse absent return/caller/UUID/root/nonce/code joins, and reject rewritten or
reset native history. Additional no-build source/factory tests and actual
Node/fixture/AFC routes inspect the wired native boundaries. Native dispatch,
factory timing, callbacks and weak retirement still require compilation and
separately authorized device qualification.

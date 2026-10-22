# iOS ordinary Avatar and People controls

Feature 3/14 remains partial until the complete observation, peer, images and
cleanup join exists. This component delivers ordinary input and retains its
original ownership; it does not report an avatar or relationship outcome.
Native sources remain uncompiled and devices untested.

`native/NormalAvatarControls.h` inspects the actual selected `AvatarApp.qml`
and `Pal.qml`, their original QML IDs, runtime peer rows, current URL/favorite
drafts, Settings scale slider, wearable choices and actual consent panels.
Native file QML must come from the current app bundle. Root UUIDs identify real
retained QML objects. The normal source birth is independent of tablet
visibility; each input separately retains its actual original root, token,
draft/dialog/selection context, native sequence and geometry.

`adapters/avatar_controls.py` provides the typed original survey and existing
iOS native Qt transport. Inputs use genuine pointer events, focused native IME
replacement, slider pointer positions and normal Home/Down/Return keys for an
already focused wearable choice. No QML handler, model/bookmark/entity setter,
social response setter or expected product result is invoked.

The workflow covers Avatar URL, non-overwriting Favorite save, scale, Favorite
selection/deletion, wearable URL addition, removal by the actually selected
owned entity ID, People selection/request, explicit incoming accept/decline and
normal connection removal. Each UI transition is read independently. Normal
Cancel first creates the product's terminal status panel; a separate observed
Close input dismisses it. A peer/backend result never supplies `dialog=false`.

`adapters/avatar_input_owner.py` journals each complete native command UUID and
original widget reference **before** delivery, then separately saves the
untouched native delivery receipt and advancing original readback. The private
file uses the existing 0600 atomic `PrivateFeatureState`, bounded compressed
original ledger, candidate/process/role/run/ticket binding and shared source
lock. Uncertain delivery, lost readback or an interrupted whole action remains
owned after reconstruction. Neither a fresh nonce nor replay of the whole
helper clears it. Repeated fully acknowledged action calls return the retained
input acknowledgment without sending again. Acknowledgment is never a model,
peer, render or cleanup result.

The intended source registry versions are `ios-avatar-controls: 1` and
`ios-avatar-input-owner: 1`. The source field extension is exactly
`avatarControlsVersion`, `avatarGeneration`, `avatarSourceSequence`; controls
carry actual `rootId`/`qmlSource` metadata. The existing iOS NativeInput
validator and `IOSNormalUiInput` own dispatch. The common v16 journey and its
mandatory area capability gate remain unchanged.

The whole runtime must still acquire model/failure/bookmark persistence,
loaded self/remote model and owned Hips attachment originals, authenticated
relationship rows, actual consent/callback and HTTP lifetime drainage,
independent actor publications and current challenge images. It must restore
the captured original avatar/scale/attachments/bookmarks, remove only original
owned resources, revoke authority, verify real callback/render/peer absence for
three seconds and only then retire metadata. This input owner intentionally
has no unconditional metadata-delete or synthetic cleanup-success method.

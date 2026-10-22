# iOS original Avatar model and social protocol sources

These are source-level prerequisites for Feature 3/14, Avatar/contacts. The
complete v16 area remains unadvertised. Native compilation, an actual iOS
process, a real peer, ordinary Avatar/People inputs, images and whole cleanup
have not been qualified by the host checks.

## Original model state

`adapters/avatar_state.py` retains the original request/PID/source clocks and
model generation history. Actual advertised URL, loaded Model resource,
geometry/Rig readiness, settled target/model scale and loaded bookmark rows
remain distinct. A failed missing-avatar request requires a real failed
resource callback for that exact original assignment and generation. A later
default-resource success can establish fallback without clearing that failure.
A later avatar request changes the generation; old callbacks cannot make its
failure state current. The complete original prefix is immutable.

`native/IOSAvatarStateObservation.h` supplies a GUI-thread native bracket and
passive bounded history. The source is compiled only for
`OVERTE_E2E_FEATURE_TESTS && Q_OS_IOS`, and active only with `--testScript`.
`Model::featureGeometryWatcherIdentity()` exposes a read-only identity for
binding this source. It neither exposes the watcher object nor invokes it.

The four derived model fields and scale are prerequisites only. Bookmarks are
enumerated independently and unrelated rows must remain unchanged. Version 2
also retains strict original file bytes from the actual AvatarBookmarks service
filename, read by `IOSAvatarBookmarkFile.h` and validated in `avatar_bookmarks.py`.
The actual path uses PathUtils app data; AppLocalDataLocation is a legacy
migration input. Reads 1 and 2 are compatible, but version 1 cannot supply this
new persistence proof and downgrade after version 2 is rejected. A requested wearable
URL, model response, HTTP receipt or Add button cannot supply wearable geometry.

## Shared native integration manifest

Shared dispatch and native owner files are reserved to the integration owner.
The additions below must be applied together before the source is callable.

1. Include `IOSAvatarStateObservation.h` under the existing E2E+iOS guards in
   MyAvatar and TestScriptingInterface. In the MyAvatar constructor, immediately
   after creating `_skeletonModel`, call:

   ```cpp
   overte::e2e::IOSAvatarModelHistory::instance().bindWatcher(
       _skeletonModel->featureGeometryWatcherIdentity());
   ```

2. Immediately before `Avatar::setSkeletonModelURL(skeletonModelURL)` in the
   actual MyAvatar setter, record the expanded original requested URL:

   ```cpp
   overte::e2e::IOSAvatarModelHistory::instance().requested(
       skeletonModelURL.isEmpty() ? AvatarData::defaultFullAvatarModelUrl() : skeletonModelURL);
   ```

3. **Do not connect the URL-less `Model::setURLFinished(bool)` as model failure
   provenance.** A queued old completion could observe advanced current
   properties. In `GeometryResourceWatcher::setResource`, immediately after the
   actual `_resource = resource` assignment, add this separate passive observer
   under the E2E+iOS guard. Include the native header using the reviewed relative
   path from `libraries/model-networking/src/model-networking/ModelCache.cpp`:
   `../../../../tests/device/native/IOSAvatarStateObservation.h`.

   ```cpp
   if (_resource) {
       const auto original = overte::e2e::IOSAvatarModelHistory::instance().resourceAssigned(
           this, _resource->getURL(),
           QString::number(reinterpret_cast<quintptr>(_resource.data()), 16));
       if (!original.isEmpty()) {
           if (_resource->isLoaded()) {
               overte::e2e::IOSAvatarModelHistory::instance().finished(original, true);
           } else {
               connect(_resource.data(), &Resource::finished, this, [original](bool success) {
                   overte::e2e::IOSAvatarModelHistory::instance().finished(original, success);
               });
           }
       }
   }
   ```

   The additional connection captures the original assignment before product
   delivery. It does not alter the product's existing start/stop connections,
   old queued callbacks, cache, retry or fallback behavior. Old callbacks retain
   their original resource identity, URL, assignment and requested generation.
   The callback captures no resource owner or pointer to dereference later.

4. Add the existing-style TestScriptingInterface `featureIOSAvatarState`
   entrypoint, member `std::shared_ptr<overte::e2e::IOSAvatarStateObservation>`,
   and fixed `saveObject` filename allowlist. Validate exactly
   `{schemaVersion,commandId,action,runId}`, schema 1, `ios-<32hex>`, `<32hex>` and
   action `feature-ios-avatar-state`. Require current actual lifecycle and
   `--testScript`; marshal to the GUI thread with checked invoke result.
   Read actual MyAvatar/model/AvatarBookmarks values in the bracket callback:

   - `sessionId`, `requestedUrl`, `resourceUrl`, `defaultResourceUrl` as exact
     current native values, not supplied expected inputs;
   - `geometryLoaded = model->isLoaded()`;
   - `rigReady = geometryLoaded && model->getRig().getAnimNode() != nullptr &&
     !avatar->getJointNames().isEmpty()`;
   - `shouldRender`, `targetScale`, `modelScale`, `jointNames` from the actual
     native avatar/model;
   - `bookmarks = {source:"AvatarBookmarks.getBookmarks", entries:getBookmarks(),
     loadError:!getBookmarkError().isEmpty()}`.

5. Register the closed fixture command and existing probe dispatcher;
   dispatcher calls `Test.featureIOSAvatarState(command)` exactly once and saves
   the untouched original as `feature-ios-avatar-state.json`. Missing API must
   return unavailable. Add the existing candidate-bound HTTP/AFC reader factory
   returning `IOSAvatarState`, using the actual native clock and process guard.
   The current `ios-avatar-state` producer is version 2, with reads 1 and 2.
   Its callback also reads `bookmarkFile` using the guarded actual native
   `AvatarBookmarks::featurePersistenceFileName()` and `IOSAvatarBookmarkFile`.
   The separate original-file grammar is `ios-avatar-bookmarks` version 1.

## Controlled social backend

`feature_journeys/avatar_social_provider.py` implements the actual protocol
used by `peopleConnection.js`, `pal.js` and the original `request.js`:

- POST `/api/v1/user/connection_request` receives the wrapped JSON participants;
- GET on that path receives actual `node_id`/`proposed_node_id` query fields;
- GET `/api/v1/users?filter=connections&per_page=400` independently enumerates
  actual relationship rows, including the original optional `search`;
- GET `/api/v1/users/connections?per_page=1000&page=1&sort=username,ASC` supplies
  the actual Pal PSFListModel connections table and original pagination fields;
- DELETE `/api/v1/user/connections/<username>` removes the owned relationship.

An actual POST from **each** separately authenticated account is mandatory.
Polling, peer Messages and fixture control calls cannot consent for an account.
Pending requests expire after 12 seconds, matching the product's bounded server
confirmation phase. Cancel/reject before acceptance makes no POST in the
product, so no relationship is created. The provider cannot send an invite,
accept a prompt, simulate the real peer or report a model/render effect.

`avatar_social_http.handle(handler, parsed)` integrates into the current HTTPS
handler immediately after the adapter-role write restriction and before account
or generic resource dispatch. It returns False for unrelated paths. It requires
the original trusted TLS 1.2/1.3 listener; no HTTP downgrade or trust bypass is
added. Existing `Handler.send` records real status/response ID/complete socket
write bytes/hash. The provider retains a missing/mismatched write as unresolved
ownership. Requests/history remain private; snapshots copy original records.

Construct `AvatarSocialProvider(account_authenticator(account_provider))` and
attach it as `server.avatar_social_provider`. Use two independently provisioned
existing AccountProvider runs/principals and actual independently read avatar
session IDs and domain when provisioning the social run. Activation uses the
current fixture ticket. The existing runner-only reader or actor source may
read its snapshot, while the adapter receives only its read-scoped channel.
Never give the adapter publisher/control authority. Retire only after actual
relationship absence, expired pending requests, all writes, zero inflight
requests, authority revocation and the whole-journey quiet proof. Neither
`revoke` nor `retire` silently deletes relationships.

## Remaining whole-area integration

Ordinary original Avatar/People controls and their retained callback sources,
wearable Model resource/attachment observations, actual bookmark file bytes,
real mutually consenting peer and native authenticated HTTP read history,
fresh challenge images, durable input owner, independent publisher and three
seconds of proven full cleanup are still mandatory. No complete capability is
enabled by these components or by the tests.

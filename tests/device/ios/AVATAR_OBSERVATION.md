# Avatar and People source observations

Feature 3/14 remains partial. These sources and their host checks are integrated
prerequisites, not a complete feature capability, compiled native qualification
or a real peer/device result.

`IOSAvatarRenderersObservation` writes version 4; the strict reader accepts
versions 1, 2, 3 and 4 without manufacturing missing fields. Version 2 adds actual
joint-name-to-runtime-index mapping. Compact `Avatar::getJointNames()` order
cannot supply a runtime Hips index. Version 3 adds separate original
`externalPose`. Version 4 adds actual mesh bounds and defines Rig readiness
using the actual animation skeleton, which remote avatars also possess. A local
animation graph is not a remote Rig readiness condition. Older packets remain
readable but cannot satisfy the current complete remote join. `boundsReady`
requires loaded renderable mesh geometry without pending scene fixup. Native
`Avatar::getBounds()` requested-scale fallback boxes are never emitted as
actual render bounds.

Remote `OtherAvatar` interpolates actual received joint history, copies those
joints into its Rig and calls `computeExternalPoses()`. The passive hook runs
after `_externalPoseSet = _internalPoseSet`, while the original write lock is
held. Its separate read lock returns unchanged original Rig birth, ID, copy
serial, native capture time and complete bounded relative joints. Reading the
source never increments that serial or retimes those poses. A pose above the
bounded complete size is unavailable. Remote poses have no local animation
graph/clip/override requirement. The existing local animation getter and its
local evaluation serial cannot stand in for this remote source. Received packet
and rendered pose observations remain separate originals: interpolation means
the latest packet is not necessarily identical to the current rendered pose.

`AvatarSocialHttpObservation` writes original native XHR events for installed
`request.js` calls from actual Pal, peopleConnection or request-service script
contexts. The actual original defaultScripts manager membership and submitted
code identity accompany the context URLs. These URL/membership records do not
claim a CommonJS module-code digest. Original method/URL/request body bytes,
response header ID/body bytes/status, request.js responseText access during an
actual callback, timer/callback/reply/XHR lifetime events are retained without
recording OAuth tokens. Snapshot does not create requests or call JS handlers.

`consumed_response` independently joins exact original provider request and
completed socket-write bytes to the actual native callback responseText read.
Provider and native clocks use separate barriers. Neither provider response
success nor this byte-consumption join establishes JSON parser success,
materialized contact rows, peer consent or full cleanup.

`IOSPeopleModelObservation` reads the actual selected installed Pal QML and
retains previously seen roots weakly through visibility changes. It enumerates
complete native models, the actual PSF pagination/request flags, original
RootHttpRequest callback keys/counter, current consent state, prompt/letterbox/
combo visibility and all three actual Pal QtQuick timer states. Hidden retained
roots continue to participate in the QML drain condition. Missing model state,
partial traversal or foreign roots do not become a successful empty table.
Actual completed contact rows and a positive native barrier are independently
required by the relationship helper. Empty loaded data while PSF requests or
refreshes remain pending cannot prove contact absence.

The existing private probe and fixed-file HTTP/AFC transport provide all three
readers with original native process/PID/birth/nonce/sequence/clock binding.
Missing native hooks save unavailable. No requested relationship, URL, scale,
joints or other wanted result is accepted as an observation command field.

Remaining full-area work includes original People protocol script timer/code
ownership, root callback delivery identity, independently published actor data,
current private GPU images and the complete durable action/recovery/cleanup
coordinator. QML-only drainage cannot replace native XHR destruction or protocol
work drainage. The full owner must restore original avatar/scale and all
unowned resources, remove only observed owned resources, demonstrate bounded
quiet using all independent original sources, revoke authority and retire its
metadata only after those obligations hold.

Host verification (native Qt/AFC documents are explicit synthetic boundaries;
OAuth, TLS, actual local file bytes and provider logic run locally):

```sh
TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/home/user/overte-ios-verification-20261021-92z8kaqy:.:tests/device \
OVT_IOS_BLOCKED_ATTEMPTS=/tmp/ios-avatar-blocked.log \
python3 -m unittest -q \
 ios.self_tests.test_ios_avatar_state \
 ios.self_tests.test_ios_avatar_bookmarks \
 ios.self_tests.test_ios_avatar_renderers \
 ios.self_tests.test_ios_avatar_controls \
 ios.self_tests.test_ios_avatar_input_owner \
 self_tests.test_avatar_social_provider \
 self_tests.test_avatar_social_http \
 ios.self_tests.test_ios_avatar_social_http \
 ios.self_tests.test_ios_people_model \
 ios.self_tests.test_ios_avatar_transports
```

Current result: 76 tests pass. No native compiler, build, simulator, device or
laboratory test was run.

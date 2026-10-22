# Original Avatar/Model load and resource sources

The E2E-only `FeatureModelLoads` helper retains bounded original request and
actual loader-callback events. `Avatar::setSkeletonModelURL` records the actual
advertised request generation. `Avatar::setModelURLFinished` records success or
failure with the actual current skeleton Model URL. The product's existing
fallback behavior remains unchanged: loading the default directly on Model
retains the advertised failed URL and Avatar generation. A later successful
requested avatar starts a new advertised generation. `Model::setURL` and its
actual watcher-finished callback have a separate original resource history.

The helper supplies neither a loaded model nor a render verdict. A consumer
must join original request and resource identities to the independently observed
loaded geometry, textures, Rig, GPU draws, actual peer and pixels. Prior failed
events cannot establish failure for a newer advertised generation.

`FeatureResourceReplies` observes actual `HTTPResourceRequest` completion before
the product consumes bytes. It uses bounded `peek`, preserving the original
consumer bytes, and records original status, native error, cache/redirect facts,
URL digests, service response ID, byte count and body digest. It retains only
closed owned avatar/dependency paths; unrelated URLs are ignored. Thread,
completion, duplicate-header, size and monotonic-clock failures keep the source
unavailable. Histories are bounded and never retimed, repaired or reset.

```sh
python3 android/phone/tests/phone-avatar-source-native-test.py --build-dir build/avatar-people-native-review
```

This command compiles and executes the real helper headers against installed
Qt6. Its explicit seams provide Model callback inputs and a synthetic
QNetworkReply; the helper verifies original generation/failure/fallback history,
retained immutable prefixes, scope filtering and unchanged consumer bytes.
`Avatar.cpp`, `Model.cpp` and `HTTPResourceRequest.cpp` product translation units
are **not compiled** by this helper check. No Android product build, devices,
actual resource transport or complete Avatar/People facade is qualified here.

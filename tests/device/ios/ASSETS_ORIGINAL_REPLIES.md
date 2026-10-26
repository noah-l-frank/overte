# Independent Assets mapping and original-source reads

The later [reply-owner version-2 packet](ASSETS_REPLY_SOURCES.md) retains exact
raw source originals with literal v1 reads and qualifies the ordinary pinned-FBX
upload/readback/client-cleanup host composition. Native/device and whole-feature
qualification remain unavailable; the original packet scope below is preserved.

This packet adds source/ownership plumbing only. Native code remains uncompiled
and device-untested. It starts no server, oven, build, installation or device
runner. Whole Assets capability, the shared dispatcher, model/texture consumer
proofs, peer rendering, bake-worker/meta/output qualification and domain-fixture
ownership remain closed.

The separate [canonical runtime connection](ASSETS_FACTORY_RUNTIME.md) now
supplies existing-session factories, final candidate/clock/AFC transport guards
and original-error-preserving read-lease cleanup. The separate
[ordinary upload vertical](ASSETS_NORMAL_UPLOAD.md) now connects rendered bundle
input and client holders to these reads. Neither packet enables whole Assets.

`networking` receives a private dedicated definition only when the existing
`IOS`, `OVERTE_E2E_FEATURE_TESTS`, and `OVERTE_IOS_E2E_TEST_BUILD` configuration
is active. Native hooks and the reader also require the actual `--testScript`
process. The standalone trace translation unit includes QtGlobal before its
platform gate. One out-of-line networking registry serves both the library
hooks and interface reader; no global/CI/production flags change.

The hooks retain actual AssetClient pending-request matches: the original
target Node control-block identity, sender Node identity, message ID, protocol
layout, original reply payload and callback arguments. Target identity comes
from the Node actually used by AssetClient, not a later NodeList snapshot.
Domain UUID is recorded at send alongside that actual target. Message objects
are held weakly, as are the original read callback controls. Callback entry and
return, request QObject destruction, observed message expiry and observed
callback-control expiry are separate facts. A returned result or cancellation
receipt cannot replace any of them.

GetAll retains actual paths, hashes, reported BakingStatus and bake error text,
including hidden mappings in the original reply. The parser checks the actual
little-endian count/string/hash/status wire representation against the native
getter result. GetMapping additionally retains its actual redirect hash/path;
a redirect or a reported status supplies no oven/completion verdict.

Raw server reads derive their hash from an original GetAll row. A real
GetAssetInfo reply supplies the measured original size first. Only positive
sizes at most 32768 bytes admit a raw read, using the existing read-only
GetAsset API with exactly that measured range. The owner joins the actual
target/sender/message, complete body, independent body SHA and measured size
back through the original GetInfo and mapping records. Companion-relative
paths remain original server paths. A final independent inventory must agree
with the initial owned-prefix rows. Input manifests provide comparison
expectations only; they cannot generate observed rows, bytes or hashes.

Successful AssetUpload stores its bytes in the local cache. A public
AssetRequest cache hit is therefore not an independent server download. This
packet does not expose a public-cache audit operation, clear caches, or label
cached bytes as fresh network replies. Passive AssetRequest boundary hooks
remain available for later properly owned consumer observations. The existing
AssetRequest `_assetRequestID` is uninitialized before cache-hit/invalid-hash
destruction; this pre-existing product limitation is documented here and is
not fixed or masked in the test build.

The native registry retains the exact serialized original result bytes and
their digest. Python verifies those bytes directly, then compares their parsed
value to the native getter snapshot. It does not assume Qt and Python serialize
Unicode or JSON identically. Bounded malformed public getter/reply values are
retained as diagnostics, while strict successful protocol joins reject them.
An unavailable server is never converted into an empty inventory.

`OwnedAssetsReplyReads` owns read leases only. It records every start/cancel
intent before transport, retains exact request/packet originals, binds the
candidate/process/session/run/ticket/resource, and recovers uncertain starts
through new observe requests. It never resends an uncertain start or cancel.
Retirement requires actual request/message/callback drain and keeps the private
closed proof; server mappings and cached bytes are untouched. The existing
twenty-second outer Assets budget applies across nested calls. Original reply
timestamps remain independent of the later observer clock. Unknown native
admission/transport outcomes remain owned and unresolved when the producer
cannot supply the original job; they are not declared empty or released.

The registry is bounded to 64 read objects and four observed message objects
per read; source replies retain at most 65536 bytes and 256 mapping rows.
GetAll itself has no pagination/size-limit protocol. These retention bounds do
not qualify unbounded remote GetAll acquisition latency or a full scenario's
native runtime budget. Actual qualified domain/server fixture ownership and
native end-to-end budget validation remain prerequisites.

Root-coordinated host entry point:

`PYTHONPATH=tests/device python3 -m unittest ios.self_tests.test_ios_assets_replies.AssetsRepliesTests`

The fixture models Qt/native/client/server boundaries explicitly. Its binary
replies and getter snapshots come from independent controlled input bytes;
Python weak references exercise real host retention. It opens no sockets and
executes no C++/Qt/device code. The host cases cannot qualify actual native
sender handling, a deployed server, model consumers, ovens or devices. No
compiler-driven `contracts/script_assets` test is included.

## Host validation

Root-coordinated run 253 passed all 15 `AssetsRepliesTests` cases. The combined
run passed 38 host cases in 21.540 seconds, including existing Tablet source
and cache regressions. The Assets cases cover original mapping/body joins,
relative companions, measured size limits, exact original result bytes,
message/control weak holds, malformed diagnostics, sender/message mismatches,
lost start/retirement recovery, unchanged reply clocks, protocol corruption,
redirect limits and unavailable-server/cache-operation rejection.

This is host model validation only. Native hooks were read-reviewed but remain
uncompiled; no actual network server, Qt callback/lifetime, installed candidate,
device, model consumer or oven result was qualified. Full Assets capability
remains closed.

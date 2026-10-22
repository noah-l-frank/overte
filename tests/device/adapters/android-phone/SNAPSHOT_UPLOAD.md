# Phone Snapshot upload originals

This packet supplies the upload/HTTPS sources used by the Phone Snapshot owner.
The complete Snapshot facade, normal capture/review inputs, Surface10,
Android Save/Share/Chooser/receiver ownership and OS target retirement remain
separate integration work. It does not enable a complete feature flag or change
global acceptance counts. The existing outer `phoneSnapshotObservationVersion`
stays **5**; the separate passive upload source is version **1**.

## Original normal request chain

The product path remains `NativeSnapshotReview.qml` → `snapshot.js` →
`Window.shareSnapshot` → `Application::shareSnapshot` →
`Snapshot::uploadSnapshot` → the existing authenticated
`AccountManager::sendRequest` and `QHttpMultiPart`. No replacement HTTP sender,
account setter or upload-success hook is introduced. Only Phone builds with
`OVERTE_E2E_FEATURE_TESTS` and a `--testScript` launch acquire the instrumentation.

The source observes the real open image descriptor's device/inode, size and
SHA. Its QFile subclass additionally hashes the bytes actually read by Qt,
without changing them or advancing the original file position for measurement.
The original AccountManager call records the actual request URL, operation,
credential presence, original multipart boundary and actual upload progress.
`jsonBytes/jsonSha256` explicitly describe the original QByteArray parameter
used by the Story request. They do not claim that the serialized multipart body
is empty. The independent HTTPS receiver supplies that complete HTTP body.

A passive finished listener is attached before AccountManager's existing
ticket/receiver callback gates. It preserves original status, network error,
response ID and bounded original reply bytes/hash, including cancellation.
Each job separately retains actual Uploader, QFile, multipart and reply object
lifetimes. A cancelled job cannot disappear while its native responsibilities
remain live. Source history is bounded, never reset, and permanently red on
overflow or clock regression. No token or Authorization value is exposed.

The original SnapshotUploader parses `/api/v1/snapshots` and then submits
`/api/v1/user_stories`, with `details` encoded as the existing JSON string.
The controlled reply returns the actual newly allocated snapshot ID and then
an independently allocated numeric Story ID with object-valued details.
Numeric IDs preserve snapshot.js's normal `parseInt` and Story DELETE path.
Actual image URLs retain `.png/.jpg/.gif` suffixes because snapshot.js uses
the original URL to distinguish GIF from still images.

## Explicit HTTPS provider and independent reads

The existing private fixture configuration opts in explicitly:

```json
{"snapshotUploadService":{"domainId":"<original non-null domain UUID>","root":"/private/empty-upload-originals","origin":"https://controlled-host:port"}}
```

The configuration also requires the existing `accountProvider: true` and
prepared trusted TLS configuration. The root must already be private, absolute,
canonical and empty of old Snapshot ownership. A new provider never adopts
another instance's retained original files. Test certificates are trusted only
by the focused host fixtures; client TLS policy is unchanged.

The original Snapshot script's domain-open query is served by the actual
`GET /api/v1/user_stories?now=...&include_actions=concurrency&domain_id=...&restriction=open,hifi`
request. Anonymous public directory access grants no upload permission. Both
native POST stages require an actual valid access token issued by the owned
OAuth provider. Foreign domain IDs, tokens, snapshot IDs, files, Story bodies,
origins and retired scopes cannot create an accepted upload. The service also
handles the normal numeric Story GET/DELETE paths.

The provider retains actual received multipart/JSON bytes and actual encoded
reply bytes as private mode-0600 files with exclusive creation and versioned
planned/opened/saved/retiring/retired ownership. Reads reopen the original
device/inode and verify actual bytes/SHA. An incomplete socket body retains its
actual received prefix and remains red. HTTP ingress begins at received headers,
so retirement cannot overtake an unfinished body read. Absolute request-body
reading remains bounded at two seconds; source reads remain bounded at five.

The response journal records independently inspected serialized status/header
identity and actual socket-write bytes/SHA. A handler return or ACK is not a
delivery proof. Native reply bytes join those original receipts. Offline input
closes the actual socket without a response; `404`, `503`, Story `404` and held
responses exercise original error/cancel paths. The ordinary `upload-fail` and
`upload` phase activations select offline and restored fixture inputs. Fixture
controls select inputs only and never publish peer samples or feature outcomes.

Read the provider at `/runs/<run>/snapshot-upload` with a fresh
`X-Overte-Snapshot-Upload-Read` nonce and the existing independent actor or
adapter-reader credential. The actor cannot obtain account credentials or set
fixture faults. Primary fixture controls and original credentials have separate
reader-only endpoints. `SnapshotUploadFixtureReader` reads phase/provider/phase
and rejects a changed ticket or origin during acquisition.

## Integration API and retirement

`adapter._snapshot_upload_source(selector).read(run)` uses only the new closed
`phone-snapshot-upload-observe` command and private
`phone-snapshot-upload-observation.json`. The separate Test method and probe
route neither capture nor cancel nor send HTTP. They preserve the original
source instance, process, command ID and acquisition clock. The shared
read-only observer gate admits this observation and rejects extra expected data.

`overte_phone_snapshot_upload_fixture.join(native_source, provider, job_id,
ticket=..., image_bytes=..., image_sha256=..., path=..., success=...)` requires
the independently acquired original capture identity. It joins actual native
consumed image bytes and boundary to the receiver's original multipart image,
then native Story JSON/reply hashes and server-generated IDs. A successful join
also requires the original permitted domain-query response in the same ticket.
The helper returns original correlated records and IDs, never a desired upload
count. Error joins require actual network error and original offline/HTTP error;
a cancelled job cannot masquerade as a completed error or success.

`require_retired(native_source)` checks every original job, including cancelled
ones, for actual terminal reply and destruction of all four native ownership
classes. The enclosing feature owner must retain initial inventories, candidate,
session/process and phase binding, both roles' fresh quiet windows and original
capture/readback evidence. It must call these independent sources again when
resuming an old retirement plan. A prior source packet is not current absence.

The service refuses retirement with ingress, held requests, incomplete writes,
foreign requests or late uploads. It verifies actual original files before
durable deletion intent, resumes a proven partial deletion, retires the owned
OAuth account and rejects files or journals that reappear after retirement.
Cleanup activation rejects new uploads. Later real requests poison retained
tombstones rather than recreating an account or accepting a retired upload.

One existing product limit stays explicit: if a queued AccountManager dispatch
finds an already invalid request ticket, its existing early return does not
release the passed multipart. The passive source retains its live file and
multipart obligations and cannot qualify retirement. This packet makes no
functional correction to that original race. The tested Cancel path first has
a real in-flight request, then performs the original normal cancellation before
its terminal reply.

## Checked scope

The focused native harness compiles verbatim actual Snapshot upload/cancel
methods, the actual `AccountManager::sendRequest` body and the complete actual
`SnapshotUploader.cpp`, together with the new passive source. Qt supplies actual
TLS, multipart serialization, file reads, event loops, a separate network thread,
request cancellation and QObject destruction. Account configuration,
DependencyManager and the UI entry are explicitly host fixtures. Five real
loopback TLS paths pass: image→Story success, offline socket close, image `404`,
Story `404` and Cancel before terminal reply. Native consumed-file SHA and both
successful reply hashes agree with the independent original receiver bytes.
Non-test launches and closed observation grammar are also checked.

Eight TLS/service tests and four strict reader/join tests reject missing or
changed original files, incomplete ownership, unresolved ingress, invalid
multipart, wrong domains/credentials/IDs, borrowed replies, incomplete native
lifetimes, partial deletion and late native/provider work. Existing Snapshot
host/native-source tests, OAuth/provider and credential-boundary regressions
are checked separately. No complete Android translation unit or APK was built;
no device, Appium, ADB, OS chooser or receiver ran. This is not device acceptance.
The integration owner retains final combined Emote source pins and global
class/SDK/count-profile updates.

Final local checks on 2026-10-22 passed: all five original native TLS paths,
all 89 Phone `test_snapshot*.py` cases (including the four upload cases), eight
receiver cases, 31 existing OAuth/provider cases, 11 fixture credential cases,
five Audio provider regressions, probe JavaScript syntax and whitespace checks.
Existing Snapshot host contracts include their prepared Java/Qt fixtures; none
of those host results establish a real Android chooser/receiver or OS deletion.

```sh
python3 android/phone/tests/snapshot-upload-source-contract-test.py --build-dir build/snapshot-upload-fresh
python3 -m unittest discover -s tests/device/self_tests -p test_snapshot_upload_service.py
python3 -m unittest discover -s android/phone/tests/device -p test_snapshot_upload_source.py
```

## Primary login credential read

The primary adapter's distinct read-only fixture token can GET the credentials
of an active Snapshot run over original TLS 1.2/1.3. This supplies only the
controlled inputs for ordinary native Login; the native/account/provider
observations must still prove actual authentication. The endpoint refuses actor
and unknown tokens, plaintext HTTP, unrelated account runs and retired runs.
Adapter POST/control/publishing permissions remain denied. Actor journals and
public feature configuration never contain these credentials. The facade clears
its temporary credential mapping after the normal Login input.

Ten real loopback TLS service tests pass, including actual adapter admission,
original credentials followed by an original OAuth grant, actor/control denials,
unrelated/retired scope rejection and plaintext refusal. These qualify fixture
access and source logic, not a Phone login or device acceptance.

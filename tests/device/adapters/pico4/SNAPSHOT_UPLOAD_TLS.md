# Pico Snapshot original TLS join

This private continuation adds the independent backend half of
[original native upload observation](SNAPSHOT_UPLOAD_ORIGINALS.md). It does not
advertise `feature.snapshots`, enter the public recipe dispatcher or establish
a normal Pico Upload/Share/Resume result. The shared v16 recipe still requires
its actual earlier Share steps and the [ordinary chooser and independent
recipient obligations](SNAPSHOT_SHARE_UPLOAD_BOUNDARY.md).

## Fixed selection and private compatibility

The selected read-only source is Phone
`b62e012f1328e30b80604bb447a60db0d8a748df`:
`feature_journeys/snapshot_upload_service.py`, only Snapshot-specific hunks in
`feature_journeys/server.py` and `witness.Client`, and
`overte_phone_snapshot_upload_fixture.py` / `overte_phone_snapshot_upload_bytes.py`.
The tests select that commit's service, byte and join checks with explicit Pico
source imports, current native metadata and additional physical/clock negatives.
No Phone facade, touch route, receiver authority, native pathname, moving worktree
or other server feature implementation is copied.

The opt-in common server accepts `snapshotUploadService` containing the prepared
`domainId`, private `root` and exact HTTPS `origin`. It requires the same original
AccountProvider and TLS 1.2+ owner. With this option absent, existing normal
fixture routing/provisioning/retirement remains unchanged. Snapshot phase and
provider activation share the existing journal lock, as does fixture retirement;
the account ticket is assigned once. The reader/independent publisher credentials
remain separate, and the adapter credential can read only. Only the adapter or
reader can obtain the owned normal-login inputs, over TLS for the actual Snapshot
run. The independent publisher cannot obtain credentials or control the backend.
No credentials, endpoints or login facts are installed into the client here.

Private `snapshot-upload-service`, `snapshot-upload-file` and
`snapshot-upload-original` are explicitly version two and read only two. They
include full original device, inode, size, mode, UID, GID, link count, mtime and
ctime nanoseconds; atime is excluded because an ordinary read can change it.
The root's actual directory identity/mode/ownership is pinned separately. Each
bounded file read checks the original FD and pathname metadata before and after,
then bytes and SHA256. The owner journal uses exact JSON types. Same-byte rewrites,
replacement, permission/link/clock changes and old five-field version-one DTOs
cannot become current originals. Device/inode and nanosecond integers here are
Python-to-Python original JSON integers; native Qt device/inode string identities
remain separately versioned and are never converted through a JavaScript number.
No legacy ownership journal is migrated or adopted.

## Actual backend originals and independent bytes

Only received HTTP requests create image/story records. A bounded original
multipart parser decodes the received image; native file reads are a separate
source. Actual wire-body/reply files have exclusive 0600 creation, durable
planned/opened/saved ownership, actual response ID/status/body write observations,
and explicit interrupted deletion intent. Ingress and in-flight requests prevent
retirement. Partial bodies, failed/foreign/late requests remain unresolved.
Transport controls select faults, not observed success or failure facts.

The provider reader validates complete source history and physical metadata.
`join()` matches actual native request URLs, reply identities/bytes/status,
consumed image bytes/hash/filename/multipart boundary, actual story JSON and the
prior actual domain-permission response. It rejects callback success alone,
borrowed receipts, altered capture bytes and cancelled jobs. Native QObject
retirement is a separate check against the original uploader/file/multipart/reply
source; matching network replies do not imply native retirement.

`PicoSnapshotUploadBytes` performs an independent authenticated TLS GET of the
retained received multipart, with proxy/redirect refusal. Its read ID is distinct
for each acquisition. The route reparses the original body after physical-owner
checks; it does not open a native capture or trust a requested image digest.
Original response metadata, received bytes/hash and decoded pixels must agree
with fresh provider observations. Binary reads retain a separate 32-MiB bound;
the existing JSON Client remains limited to one MiB. Copies and the last guard
are covered by both source-epoch and monotonic age bounds, including a frozen clock.
The caller must retain its existing exact parent/source-lock ownership; these
readers do not acquire a competing source lock or authorize an ordinary input.

## Meaning and limits of the host proof

The owning `snapshot-upload-tls` selector runs only short-lived owned loopback
HTTPS listeners with an ephemeral locally generated certificate trusted by that
test client only. It receives real multipart/image/story traffic, retains and
re-reads real private files, obtains independent bytes in both read-only roles,
handles actual socket close/404/503/permission denial and recovery, and refuses
in-flight, partial, changed and reappearing originals. Deletion-interruption
recovery uses original durable intent and does not resend a request.

The normal client/network producer in these tests is explicit Python HTTP input.
Native DTO join cases are deliberately synthetic boundaries, labelled at their
producer; they do not prove an actual client request reached the TLS fixture.
The preceding Qt harness owns actual collector/uploader bodies separately.
There is no combined native-client TLS, Android, device, rendered fidelity,
stereo, panorama, SDK26, ordinary system chooser or whole cleanup claim.

A direct test HTTP story DELETE verifies fixture semantics only. A future normal
Upload owner must cause and independently observe the original product's ordinary
story-delete path before live backend quiet. Fixture retirement can remove its
remaining server-owned images/stories; that removal is not a client cleanup fact.
It must follow the actual owning finalizer, never substitute for normal cleanup.
The service object/history stays with its live original owner; cold replacement
of a root containing existing originals fails closed. Full Upload composition
still needs the existing Still/Save parent intent, exact final phase fence before
the ordinary Upload control, original login/domain/backend binding, new native
job/replies, both independent roles, failure/recovery, return and three seconds
of actual quiet. The persistent Android export executor and missing chooser/
recipient paths remain explicit whole-feature boundaries.

The final source-clock read precedes the final monotonic recheck. A slow clock
transport cannot escape the acquisition age bound while returning a frozen epoch.

A partially executed fixture deletion is not a fresh retained-file observation.
Provider snapshots and binary reads fail while any required wire owner has
entered retiring/retired before its request completes retirement. The original
durable deletion intent still allows the owning finalizer to resume cleanup.

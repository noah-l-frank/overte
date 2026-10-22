# Independent controlled Snapshot Documents provider

The existing separate debug fixture APK also exposes a normal DocumentsProvider
at `org.overte.e2e.snapshotreceiver.documents`, protected by the platform's
`MANAGE_DOCUMENTS` permission with normal document URI grants. DocumentsUI displays
the armed root as **Overte Snapshot Evidence**. It creates an actual private PNG
and the normal Phone ContentResolver output stream writes that same file.
The provider and its evidence owner never initialize, arm or retire the separate
ACTION_SEND Consumer. The existing installed fixture APK/PID/start/UID/digest
qualification remains mandatory in the host reader; a prepared signed APK needs
its own externally reviewed APK SHA pin.

The DUMP-protected `.evidence` provider has a disjoint protocol:

- `documents-arm`, exactly `runId` and `armId` (lowercase hex32 strings).
- `/documents-observations/RUN/FRESH_NONCE`, read-only original JSON.
- `/documents-originals/RUN/DOCUMENT_ID/FRESH_NONCE`, original bytes, at most 32 MiB.
- `documents-retire`, exactly `runId`.

All control returns are ACKs. No command supplies a path, content URI, filename,
bytes, digest, writer UID or desired result. Observation and binary nonces are
single use and independently bounded to 4096. One process can arm once. An old
`overte-snapshot-documents-*` private root prevents fresh owner construction.
There are at most 64 original creation plans and 4096 descriptor/transfer records.

Normal `createDocument` accepts only the actual armed `root-RUN`, MIME
`image/png`, and display name `e2e-RUN-[A-Za-z0-9_-]{1,160}.png` from normal
native export. It allocates the opaque ID `doc-RUN-ARM-RANDOM32`; paths derive
only from this owned ID under the newly created private mode-0700 root
`files/overte-snapshot-documents-RUN`. Original mode-0600 regular files must retain
their original device/inode/file key, one link and unchanged root/parent.

Actual `Binder.getCallingUid()` supplies creation and open identities. Only
`r` and one `w` writer are admitted. Actual PFD fstat must match the original
file and storage UID. Successful OnCloseListener callbacks supply the actual
descriptor close; only a successfully closed writer permits the independent
original file hash/size to be published. Empty/oversized/changed data or failed
close keeps the source incomplete. PNG decoding/content comparison remains a
separate mandatory host image check; MIME alone proves no image.

## Exact original JSON v1

Top-level keys are exactly `snapshotDocumentsVersion`, `runId`, `armId`,
`observationId`, `instance`, `sequence`, `capturedEpochMs`, `processId`,
`providerUid`, `providerPackage`, `complete`, `root`, `plans`, `documents`,
`fdLifetimes`, `retired`, `workersTerminated`. Version is integer 1; run/arm/
observation/instance are hex32 strings; sequence is advancing positive integer.
Time is original positive wall-clock milliseconds, never host substitution.
PID/UID/package come from the actual provider process. Package is
`org.overte.e2e.snapshotreceiver`. `complete`, `retired`, `workersTerminated`
are booleans. No field is nullable. `workersTerminated` requires retirement,
actual HandlerThread termination and all previous source pipe writer/deadline
threads terminated. Each current source transfer is bounded by its own real
pipe EOF/close and 15-second watchdog; acquire a subsequent fresh observation.

`root` has exactly `rootId`, `path`, `device`, `inode`, `present`,
`checkedEpochMs`. Device is nonnegative integer; inode positive; `present` is
boolean. Its original identity remains in the source after verified absence.

`plans` entries have exactly `documentId`, `createUid`, `createdEpochMs`,
`displayName`, `mimeType`, `phase`. The UID/time are actual original creation
callback values. Phase is `planned`, `created` or `failed`, recorded before file
allocation; an unresolved plan is retained, never silently erased/adopted.

`documents` entries have exactly `documentId`, `uri`, `displayName`, `mimeType`,
`createUid`, `createdEpochMs`, `device`, `inode`, `bytes`, `sha256`, `writerUid`,
`writeOpenedEpochMs`, `writeClosedEpochMs`, `deleteCalls`, `deletedEpochMs`,
`absent`, `checkedEpochMs`. URI is the exact `.documents/document/DOCUMENT_ID`.
Initially bytes/writer/open/close are zero and SHA is empty. A successful writer
close publishes bytes 1..33554432, lowercase SHA64, actual positive writer UID,
and open/close times (close >= open). Until then close remains zero and no
successful original is available. `deleteCalls` is 0 or 1; deletion time is
zero until successful actual unlink. `absent` is boolean and checked time starts
at zero, then records an independent actual absence check. Historical deleted
rows remain; original data/hash/creation identity do not change.

`fdLifetimes` entries have exactly `id`, `documentId`, `mode`, `callerUid`,
`openedEpochMs`, `closedEpochMs`, `closed`, `error`. ID is hex32; mode `r`/`w`;
caller UID positive. Both flags are boolean. Open time is positive after actual
open, zero only for a reserved/failed open. Close time is zero while open and
positive after actual close/failure callback. An unopened/failed callback makes
`complete=false`. There is no successful inferred close from an input ACK.

## Native ownership and retirement

Custom normal query columns, in addition to standard Document fields, are
`overte_run_id`, `overte_arm_id`, `overte_provider_instance`, `overte_create_uid`,
`overte_created_epoch_ms`, `overte_writer_uid`, `overte_write_opened_epoch_ms`,
`overte_write_closed_epoch_ms`, `overte_device`, `overte_inode`, `overte_sha256`,
`overte_delete_calls`, `overte_open_descriptors`. These are actual original state,
not values supplied in a lab control request. The last column counts unclosed
normal document descriptors and is not an additional JSON DTO field.

The native query uses this exact ordered projection: `document_id`,
`_display_name`, `mime_type`, `overte_run_id`, `overte_arm_id`,
`overte_provider_instance`, `overte_create_uid`, `overte_created_epoch_ms`,
`overte_writer_uid`, `overte_write_opened_epoch_ms`,
`overte_write_closed_epoch_ms`, `overte_device`, `overte_inode`, `overte_sha256`,
`overte_delete_calls`, `overte_open_descriptors`, `_size`.

Transport shape example (synthetic IDs only, not execution evidence):

```text
call content://org.overte.e2e.snapshotreceiver.evidence
  method=documents-arm extras={runId: aaaa...32, armId: bbbb...32}
read content://org.overte.e2e.snapshotreceiver.evidence/documents-observations/aaaa...32/cccc...32
read content://org.overte.e2e.snapshotreceiver.evidence/documents-originals/aaaa...32/doc-aaaa...32-bbbb...32-dddd...32/eeee...32
call content://org.overte.e2e.snapshotreceiver.evidence
  method=documents-retire extras={runId: aaaa...32}
```

The control transport passes strings via Bundle extras and receives only
`{"accepted":true}`. Read transport returns UTF-8 JSON/raw bytes through a reliable
PFD pipe and must read EOF and close it. The JSON source uses an original new
observation ID, advancing sequence/time and actual provider process identity.
Prewrite `bytes=0, sha256="", writerUid=0, writeOpenedEpochMs=0,
writeClosedEpochMs=0` is legitimate original state; it is not a written file.
While an FD is reserved but not yet actually opened, its zero open time makes
the current source `complete=false`; successful actual open resolves that
transient condition. Failed callbacks keep completeness false.

Native `SnapshotOsDestinations` uses source version 2 only when it owns a
`.documents` destination. MediaStore version-1 identity semantics stay unchanged.
The original SAF callback retains `inserted=false`. The fixed E2E-only
`Access.createdHere()` branch qualifies the original new fixture creation and
actual Phone writer before one-send native cleanup. General SAF remains refused.
Document identity is exactly `uri`, `providerUid`, `providerPackage`,
`ownerPackage`, `displayName`, `device`, `inode`, `storage`, `runId`, `armId`,
`providerInstance`, `documentId`, `createUid`, `createdEpochMs`; storage is
`documents`. The actual provider package and its matching fstat storage UID
supply ownerPackage, which is the fixture package, not the Phone package.
The separate provider source supplies the actual writer UID and closed bytes;
the host must join that UID to the independently qualified Phone UID.

Native cleanup rechecks unchanged identity/bytes, actual closed Phone writer and
zero pending provider FD callbacks, then calls normal
`DocumentsContract.deleteDocument` once. Its ACK cannot prove deletion. A normal
query must return zero rows and original open must throw FileNotFoundException.
The provider records only actual unlink and independently checks absence; it
refuses deletion with open descriptors, changed bytes/inode or a second call.
Retirement requires all documents absent, all FDs/source transfers closed, an
actually empty original root, successful root deletion and callback thread
termination. Later original-name/root resurrection stays red. Unknown files are
preserved. Docs-only cleanup neither initializes nor retires Consumer state.

## Verification limits

Host tests execute actual Java file/hash/stream/thread ownership, the original
DocumentsProvider callbacks and native SnapshotOsDestinations/Owner, with
explicitly synthetic Binder/PFD/ContentResolver/Handler/Os API seams. The native
test also runs original false-insert SAF callbacks, delayed actual close,
uncertain actual delete return, and fresh query/open absence. The real provider
callback test prevents an expected post-delete FileNotFoundException from
poisoning source completeness. Prepared API34 compilation/dex/aapt2 creates
an unsigned, uninstalled fixture APK; the actual native SAF Java glue is also
compiled against API34. These checks do not execute Android DocumentsUI, Binder,
URI grants, ContentProvider/PFD callbacks or SDK26–28 runtime behavior. No device
test, installation or physical acceptance has been performed.

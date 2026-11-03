# Lossless Close original storage, version 2

New private Close original containers use `snapshotCloseOriginalsVersion:2`.
The Close owner stays version2 and its source acquisition, inputs, controller
Session, original clocks, quiet windows, cadence and deadlines are unchanged.
The previously exported `snapshot_close_owner.SnapshotCloseOriginals` name now
imports the compatible class from `snapshot_close_originals`.

A complete acquired Close frame includes the unchanged `base`, `upload`,
`provider`, `account` and original `hostMonotonic`. Version2 stores it as one
`fullFrame` original in the existing immutable `ChatSourceChunks` container if
pure serialization proves that it fits the existing pack bound and the entire
physical child plus its final newline fits64KiB. Otherwise the encoded row has
explicit `roleFrames` references to the same four original components and its
original host time. Neither format projects or reinterprets a producer DTO.
Capacity selection happens before any write. File, namespace, descriptor,
physical-identity, guard and CAS exceptions propagate; none select fallback.

The whole input graph must consist of exact JSON DTO types before any source
write. Tuple/list aliases, subclasses, coerced dictionary keys and nonfinite
values cannot acquire a digest-based shortcut. Complete original references
are reused after admission. A later host-only controller-envelope CAS does not
recompress unchanged original frames and cannot create a root or child for an
unknown frame. It still verifies the complete namespace and every retained
physical signature. The underlying immutable-byte/hash, file-reading, original
scope, pending-write and CAS predicates are unchanged.

The original per-container512-part,16MiB decoded-history and64KiB file bounds
remain. Complete serialized originals are counted by `ChatSourceChunks`,
including the original wrapper. Parent references and all other containers
remain part of the separately measured whole namespace bill. This change
introduces no new global budget exemption or retirement authority.

An existing version1 container is read and continued as version1 without
rewriting or migrating old parts. Its original four-role grammar and scope
hash remain unchanged. Missing or foreign parts, rootless or uncommitted child
files and unknown manifests cannot be adopted as a new owner. Passive cold
reading validates its retained bytes and scope; as before, it cannot recover
a former warm reader's lost inode identity or claim native freshness. The
Upload and Background original containers keep their original version1 defaults.

## Verification

The dedicated disjoint `test_snapshot_close_originals.py` selection exercises
complete-frame roundtrip, real incompressible fallback, legacy continuation,
unchanged Upload/Background defaults, strict DTOs before writes, zero-write
host-only rejection, original-reference reuse, missing/changed/foreign/orphan
parts, warm same-byte inode replacement and unknown child/manifest CAS.
Unknown writes retain the original pending responsibility and do not try the
other layout. The original decoded-capacity and exact reference guards remain: more than
14MiB of genuine decoded originals are retained before the next actual
2MiB original exceeds the unchanged16MiB history limit, with no child/root
write at refusal.

Actual retained originals from the earlier continuous99.130s warm run were
also read directly:34 frames/136 version1 parts and1,170,837 decoded bytes.
Historical decode and an unchanged host-only encode issued zero source queries,
inputs or writes. All original namespace bytes and eight-field physical
identities matched before/after. This supplies compatibility evidence only;
it grants no live authority to the old uncertain or completed run.

The current unchanged continuous warm selection passes in95.441s under the
original120s limit;234 loaded source SHA-256/eight-field physical identities
are unchanged. The disjoint eight-case storage selection passes in0.590s
with48 loaded sources unchanged. Both original process handles are terminal.
No source/compiler build, product process or device was invoked.

| Actual complete Snapshot namespace | Previous Close1 | Current Close2 |
| --- | ---: | ---: |
| Files, including the original nested return PNG |543|441|
| Immutable history parts, all containers |520|418|
| Stored bytes, including manifests/parents |1,708,110|1,603,278|
| Container decoded history bytes |4,816,400|4,816,026|
| Decoded parent payload bytes |120,700|106,860|
| Total of both decoded bills |4,937,100|4,922,886|
| Complete Close frames |34|34|
| Close immutable parts |136|34|

The original Cancel/Save/failed-upload/upload/background/Close frame counts
remain82/33/17/21/16/34. The retained original inventories contain the same
729 distinct request IDs and858 command IDs,35 distinct normal QML input
commands and the same original tablet-open/tablet-close envelopes. All34
Close host-monotonic values also match exactly. These inventory counts come
from the complete immutable histories and owner payloads, including embedded
raw JSON; they are not extra source calls or a trace of callback invocations.
Every original is retained and the full before/after file hash/physical
namespace bill is preserved. The102-part reduction is lossless composition;
no old source file was removed, retimed or reused as a new observation.
These are two fresh runs with their own IDs/paths and normal source values;
small byte-size variations outside Close are included in the actual bill.
The global namespace now fits512 history parts and16MiB decoded storage for
this component. No new global admission/cleanup authority is inferred from
that measured finite run.

Native Qt,
JS, SDK, rendering and Android clocks remain explicit host fixture producers.
Actual hardware, independent image/Actor evidence, whole Common16, raw Settings
restoration, OS Share and global final retirement remain unqualified.

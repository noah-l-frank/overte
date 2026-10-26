# Assets file-owner source storage

The actual pinned 25,196-byte FBX fits the existing native per-file/body limits
but the previous inline owner history exceeded the 48 KiB packed-parent limit
while staging it. File-owner version 2 stores a small controlled-input manifest
and private immutable references instead. Input pins, native versions, the
48 KiB packed limit, 64 KiB owner-file limit, 16 MiB expanded-state limit,
128-observation limit and native freshness/candidate checks remain unchanged.

The owner reconstructs only controlled test INPUT bytes from their unchanged
pins and verifies the saved manifest. Native observation strings are retained
verbatim in immutable `assets-files-native` frame files with the original
query, SHA, byte count, process/session/run/role and actual file identity. Typed
history replay reopens and validates these originals; it neither reconstructs
observations from inputs nor retimes old native clocks. A subsequent native
request still requires the current guard and a fresh native reply.

Each source intent is durable before allocation/write, and each opened file
identity is durable before its body is written. A complete saved source can be
adopted after a lost parent update using only its original bytes; no query or
stage mutation is resent. An interrupted source retains its exact prefix hash
and length and blocks further source delivery/retirement. A second failure
while saving that prefix preserves the original exception and the existing
blocking owner. A closed host descriptor does not establish native weak-owner,
callback-body, server or oven retirement.

Literal version-1 owners remain readable. Migration first saves an exclusive
immutable frame containing the exact old owner-file bytes and identity, then a
private migration journal, before replacing the parent. A saved child survives
a lost parent CAS without rewriting or resending. An incomplete migration is
inspected as outstanding responsibility, with its exact partial prefix; it is
never adopted as complete. Historical session inspection recognizes only the
exact owned source/journal membership and records actual original-file reads.
Orphan files, changed bytes/inodes, foreign role/context and missing carriers
cannot become an empty ownership census. Old picker and successor phases are
unchanged.

## Verification and limits

`test_ios_assets_file_storage.AssetsFileStorageTests` passed 14 cases in
2.306 seconds (`.ios-host-tmp/assets-file-storage-v2-final-parser-20261026.log`).
The actual pinned FBX stages and is removed only after the independent modeled
native UI/work census permits release. Tests also cover verbatim alternative
JSON formatting, equal-byte replaced inodes, manifest/role rejection, saved
source recovery, nonempty interrupted prefix preservation, primary error
preservation, exact v1 migration/parent-CAS recovery, migration-journal identity,
observed v1 clocks/current-guard continuity, orphan refusal and a real host weak
consumer with pending callback body blocking release. Real host files, fsync,
locks, hashes and inodes are used; Qt/native/device acquisition is explicitly
modeled by the existing original-QML Node fixture.

Before the final adjacent expanded-limit/membership/error-preservation checks,
38 cases passed in 95.275 seconds, including the then-12 storage cases,
12 original picker cases, 10 canonical factory/transport cases and four pure
ownership cases (`assets-file-storage-v2-compatibility-20261026.log`). The final
14-case selection includes the subsequent changes. These selections invoke
only the reviewed host Python/Node entrypoints, with private TMPDIR and no
compiler, native binary, device or actual server/oven/service.

The final focused command was:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=.:tests/device:tests/device/self_tests:tests/device/ios/self_tests \
TMPDIR="$PWD/.ios-host-tmp" timeout 60s python3 -m unittest \
  test_ios_assets_file_storage.AssetsFileStorageTests -v
```

The contract-version validator passed, and the documentation checker passed
all 802 workspace Markdown files without fetching remote URLs.

This resolves the measured storage prerequisite; it does not qualify an actual
ordinary FBX upload, bake, rendering, publication or backend cleanup journey.
The later [reply-owner packet](ASSETS_REPLY_SOURCES.md) separately qualifies the
ordinary pinned-FBX upload/readback/client-cleanup host composition.
Next compose the durable normal bake/import owner with actual worker/meta/output
observations, model/resource consumers, independent rendering/publication and
paired cleanup. Full Assets capability remains closed and source completion
remains 5/14.

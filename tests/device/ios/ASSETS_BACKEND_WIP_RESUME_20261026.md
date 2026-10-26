# Assets backend WIP pause: 2026-10-26

Resumed after this historical pause: the closed Python source/collector/domain
route packet now has 32 passing host cases. See `ASSETS_BACKEND_SOURCE.md` for
the current exact results and limits. The saved native hooks remain uncompiled;
backend retirement and complete Feature 13 admission are still unfinished.

Feature 13 remains closed. The completed ordinary mapping tree packet is
`392d0cd635`; its three host whole-flow cases passed before this backend work.
The source-complete area count remains 5/14. This new backend packet is a
deliberately uncompiled, untested and unconnected draft, saved for user pause.
No compiler, device, server, oven, laboratory, installation or remote write ran.

No backend tests have started. The announced selection
`test_asset_backend_source.BackendWorkTests` and
`test_asset_backend_source.BackendSourceTests` (12 cases) was cancelled before
launch when the pause arrived. No own test, native or service process remains.
There is therefore no backend test log or backend qualification result.

## Exact draft ownership

Eight conditionally instrumented original product files:

- `assignment-client/src/assets/AssetServer.cpp`
- `assignment-client/src/assets/AssetServer.h`
- `assignment-client/src/assets/BakeAssetTask.cpp`
- `assignment-client/src/assets/BakeAssetTask.h`
- `assignment-client/src/assets/SendAssetTask.cpp`
- `assignment-client/src/assets/SendAssetTask.h`
- `assignment-client/src/assets/UploadAssetTask.cpp`
- `assignment-client/src/assets/UploadAssetTask.h`

Six new source/test files, plus this handoff:

- `tests/device/native/AssetBackendWork.h`
- `tests/device/native/AssetBackendFiles.h`
- `tests/device/native/AssetBackendQuery.h`
- `tests/device/adapters/asset_backend_work.py`
- `tests/device/adapters/asset_backend_source.py`
- `tests/device/self_tests/test_asset_backend_source.py`
- `tests/device/ios/ASSETS_BACKEND_WIP_RESUME_20261026.md`

No backend registry, build option, domain route, collector, fixture process
launcher, installed adapter or capability configuration was edited. Other
agents' work in the worktree must be preserved and excluded from this packet.

## Draft behavior and limits

All native hooks require the existing default-off `OVERTE_E2E_FEATURE_TESTS`
gate and Linux, an already owned process token and a canonical private 0700
source directory in `OVERTE_E2E_ASSETS_SOURCE_ROOT`. Product behavior, task
scheduling, permissions and `BakeAssetTask::isBaking` remain unchanged.

The proposed source binds actual server/domain UUIDs, process ID, source/data
root inodes and owner-token SHA. A fixed closed passive query cannot contain
desired mappings, paths or hashes. Exclusive intent/original/saved files retain
actual bytes, hashes and stat identities; the latest edit adds directory fsync
after immutable file fsync. Partial or uncertain writes are never overwritten.
This protocol has no actual collector or domain route yet.

The draft snapshot reads original memory/persisted mappings, hash-directory
membership, bounded blob/meta bytes, native Node write permissions and actual
pool/queued counts. Oversized bodies remain unknown. Task leases hold only a
sidecar token; the observer keeps weak references to actual Bake shared owners
and QObjects. Run and signal-callback body returns remain separate from weak
expiry. Sticky `isBaking`, callback completion, UI disappearance and mapping
absence cannot establish backend retirement.

Python draft parsers check exact schemas, event-prefix continuity, bounded raw
body/hash/map/meta joins and the independent backend clock domain. The proposed
12 tests use real temporary files/stat/SHA and Python weak references while
explicitly modeling native/Qt/AssetServer/oven/clock boundaries. They cannot
qualify the uncompiled C++ source. AST parsing of both codecs passed before the
test file was authored; no test execution followed.

## Next authorized resume step

Review the entire draft and its entrypoints, then run only those explicit
12 host cases, bounded to 120 seconds, after the normal shared-source/test
coordination. Use the existing worktree environment:

```
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=.:tests/device:tests/device/self_tests:tests/device/ios/self_tests
TMPDIR=$PWD/.ios-host-tmp
```

First check event/weak lifetime grammar against actual C++ field names and
counterexamples where all weak holders expire before an original body returns.
Review query durability, filesystem consistency limits and malformed/incomplete
diagnostics. Never infer a qualified empty snapshot from missing hooks.

Then implement an independently owned domain collector using actual /proc
process-start/role/token/executable identities and original source admissions,
with immutable intents and no unknown-query resends. Coordinate before editing
shared fixture/domain routes, registry or adapter code. Independent namespace,
hidden meta/baked mappings, unshared/shared blob retirement and native-plus-host
quiet windows still need a complete owner; `server-retirement` remains open.
Normal bake controls, Add to World/model consumers and whole-journey admission
also remain unfinished. Do not enable Feature 13 from this partial draft.

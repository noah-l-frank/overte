# Exact Assets reply originals and ordinary FBX upload

The first fresh normal pinned-FBX upload reached original-QML upload completion,
then failed in independent raw-server readback: the reply owner's inline bodies
exceeded the existing 48 KiB packed-parent limit. File-owner version 2 had
resolved the separate INPUT staging overflow. Neither fix increases a body,
packing, fixture-pin or protocol limit.

Reply-owner version 2 stores unchanged command/job/lease metadata and small
immutable raw-source references. Actual native reply strings, including the
independent original binary body and result bytes, are retained verbatim under
the closed `assets-replies-native` profile. The default FileSources profile
keeps its original output names, keys and grammar. Namespace/schema keys are
closed class constants, never values accepted from a request or journal.

Native query/reply versions stay 1. The 32 KiB binary body, 256 KiB native source,
48 KiB packed-parent, 64 KiB private owner-file, 16 MiB expanded-history,
32-job/512-command/256-original limits and original clocks/current candidate
guards remain unchanged. Query intent precedes dispatch. Saved source bytes
survive a lost parent adoption without resending a start. Opened prefixes retain
their exact hash and size and cannot become completed reads/closed ownership.
Actual message, object, token and callback-body drainage remains separate.

Literal version-1 owners remain readable. Migration retains the exact old WAL
bytes/inode with a durable child journal before replacing the parent. Old
issued command prefixes and immutable job identity/time fields are preserved;
native JSON is never reconstructed from an expected body. Saved children survive
lost parent CAS; incomplete migration remains blocking. Historical inspection
validates exact carrier/journal membership and orphan/partial responsibility
without querying native state or inventing a fresh timestamp.

## Verification

New `AssetsReplyStorageTests`9, existing `AssetsRepliesTests`15,
`AssetsFileStorageTests`14 and `AssetsRuntimeTests`10 passed: 48/48 in 13.933
seconds (`.ios-host-tmp/assets-reply-storage-first-20261026.log`).

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=.:tests/device:tests/device/self_tests:tests/device/ios/self_tests \
TMPDIR="$PWD/.ios-host-tmp" timeout 120s python3 -m unittest \
  test_ios_assets_reply_storage.AssetsReplyStorageTests \
  test_ios_assets_replies.AssetsRepliesTests \
  test_ios_assets_file_storage.AssetsFileStorageTests \
  test_ios_assets_runtime.AssetsRuntimeTests -v
```

The fresh unseeded ordinary-FBX composition then passed 1/1 in 17.956 seconds
(`.ios-host-tmp/assets-fbx-upload-reply-owner2-20261026.log`):

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=.:tests/device:tests/device/self_tests:tests/device/ios/self_tests \
TMPDIR="$PWD/.ios-host-tmp" timeout 180s python3 -m unittest \
  test_ios_assets_fbx_upload.AssetsFbxUploadTests.test_original_normal_fbx_bundle_upload_independent_bytes_and_client_cleanup -v
```

The unchanged 25,196-byte FBX travels through normal browser selection, original
bundle review/primary/destination handlers and independently serialized
mapping/GetInfo/raw-server replies. Real host bytes/inodes, original QML JS,
Python weak holders at declared native boundaries, durable originals and restart
replay execute. Client cleanup removes the staged directory after the original
UI/work/quiet checks. Pure inspection leaves exactly `server-retirement`;
picker stays `primary-chosen` and server bytes remain. The earlier failed run
ended after 5.585 seconds at the measured packed-reply limit; its upload was
never counted as a successful complete readback.

These are host source compositions with explicit native/Qt/service models,
not installed native upload or actual server/oven/device execution. No build,
compiler, service, installation or remote write ran. Full Assets capability
remains closed; source completion stays 5/14. Actual model/resource consumption,
independent rendering/publication and paired final backend/entity/resource
retirement remain open.

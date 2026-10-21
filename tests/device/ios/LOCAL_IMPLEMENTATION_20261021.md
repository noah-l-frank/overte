# iOS adapter implementation, 2026-10-21

The initial checkpoint below is historical. For current completion and remaining
work, use the [fourteen-area matrix](FEATURE_ADAPTER_COVERAGE_20261021.md),
[Script handoff](SCRIPT_FEATURE.md) and
[Authentication handoff](AUTHENTICATION_FEATURE_SOURCES.md).

## Captured source provenance

The read-only iOS reference was captured consistently with two reads.

```json
{
  "sourceCommit": "f85409d3b4b9c0c1f292b2bb5bbd903c5ff88347",
  "path": "tests/device/ios/adapters/installed_code.py",
  "patchSha256": "1abf1a201e082fb661434a455e5a356b84cd78f480bdb3c4920d5f69ce8959b8",
  "fileSha256": "0f9fb3cefdcb23094a166c2d9ec353bb39cfed8def37cfbb055d6434480a84f1",
  "capture": "double-read-consistent",
  "untracked": []
}
```

The private snapshot is outside Git with directory mode 0700 and file mode 0600.
No untracked files existed in the source capture. Both shared foundations
`7636452f2124029798948aafae70ecff5c5fa7d0` and
`0a52254c0580a1fd28626d23bead55015500c0a7` are ancestors.

## Implemented local packets

- `b38bc9c037`: captured original WIP and provenance, without editing the source.
- `1846d179a4`: selected shared fixture role separation from frozen Phone source,
  preserving the current shared provider dependencies and APIs.
- `011568ead3`: explicit one-send iOS restart launch recovery, canonical factory
  connection, immutable original proof, binding writer v3 and v1/v2 readers.
- The final handoff adds the source-based fourteen-area matrix and checks that
  every incomplete iOS suite fails its existing mandatory gate before target IO.

At this initial checkpoint the requested implementation was **not complete**.
Zero of fourteen full
v16 iOS area triples is implemented or advertised. The new work completes an
installed-code/restart recovery boundary and a shared privacy prerequisite.
The remaining per-area input/observation/independent-actor/cleanup interfaces and
next source packets are listed in
[the coverage and integration handoff](FEATURE_ADAPTER_COVERAGE_20261021.md).

## Verification

The exact private selection driver, execution guard, selected/excluded case IDs,
JSON reports and full logs remain at:

```text
/home/user/overte-ios-verification-20261021-92z8kaqy
```

Driver and guard SHA-256 values:

```json
{
  "verify.py": "2ceefe5d519007b25ed7d68740513309bc9ce37721dcd0a9f2d1ad9882e209bb",
  "sitecustomize.py": "3c1249719413b314e5a7692d8664fe986085a2e611dc73e3d1ac7b333af677e1"
}
```

The driver uses the repository's existing unittest groups; the common patterns
come directly from `run_control_plane_tests.commands('quick')`. It does not
implement a new adapter, scenario, verdict engine or device runner. It explicitly
excludes native compiler cases before class setup. Its subprocess audit blocks
actual compiler/build/device tools in parent and inherited Python processes.
The exact reviewed local Snapshot SDK fixture is allowed only by original byte
hash, private regular-file ownership/mode, absolute unaliased path and its owned
`native-snapshot-files-` directory. It executes local POSIX file scripts, never
ADB or a device connection.

Commands, from this worktree (`verification_root` is the private directory above):

```bash
OVT_IOS_BLOCKED_ATTEMPTS="$verification_root/blocked.jsonl" \
PYTHONPATH="$verification_root:$PWD:tests/device" \
python3 "$verification_root/verify.py" ios

OVT_IOS_BLOCKED_ATTEMPTS="$verification_root/blocked.jsonl" \
PYTHONPATH="$verification_root:$PWD:tests/device" \
python3 "$verification_root/verify.py" common

python3 ios/tests/appium-native-binding-test.py
python3 tests/device/ios/test_ios_native_binding_contract.py
python3 tests/run-project-tests.py --profile quick \
  --suite documentation \
  --suite documentation-contracts \
  --suite ios-input-selection \
  --suite policy-consistency \
  --suite project-coverage --timeout 240
python3 tests/device/validate_contract_versions.py
python3 tests/device/validate_policy.py   --policy tests/device/acceptance-policy.json --catalog tests/device/catalog.json
python3 tests/device/feature_journeys/server.py --check
python3 tests/check-documentation.py --all
git diff --check
```

Results:

| Selection | Actual result | Meaning |
| --- | --- | --- |
| Broad iOS Python | 444 passed; zero failures/errors/skips | Host adapter/control logic only; 20 compiler cases excluded |
| Existing common quick Python patterns | 971 passed; zero failures/errors/skips | Shared contracts/fixtures/counterexamples; three native voice compiler cases excluded |
| Canonical binding entry | 5 passed | Original parser/owned loader with synthetic candidate/OS boundaries |
| Shared/native iOS CLI dispatch | 5 passed | Original entrypoint framing with synthetic platform boundary |
| Selected repository quick checks | 5 suites passed | Documentation, input-selection policy and coverage integrity |
| Contract registry/policy/fixtures | Passed | Original v16 inventory unchanged; 33 pinned companions/generators checked |
| Markdown | 519 files passed | Local links/anchors; no remote fetch |
| Whitespace | Passed | `git diff --check` |

The first common selection failed: its standalone driver omitted the repository
import root and its overly broad audit blocked the exact local fake `adb`
Snapshot fixture before execution. The failed log/report and blocked-fixture
records are retained as `common-initial.*` and `initial-blocked.jsonl`. No actual
ADB/device process or compiler was launched. Correcting driver import roots and
admitting only the reviewed fixture bytes produced the passing complete common
selection above. Failed attempt output is not acceptance evidence.

Explicitly unexecuted iOS native classes: all 10 methods of
`OriginalSnapshotFiles`, all nine methods of `IOSNormalSnapshot`, and
`test_acoustic_loopback.AcousticTests.test_actual_native_capture_and_script_api` (the exact class/case
IDs are in `ios-report.json`). Common exclusions are the native voice clock,
Qt recording-hook compilation and C++ generator compilation cases in
`test_voice_roundtrip.py`.

The unrestricted `ios/tests/run-tests.sh`, standard unfiltered control-plane
quick aggregate, full project quick aggregate and all native/Qt/compiler/build
profiles were not run: their transitive compiler entrypoints conflict with this
session's explicit no-build boundary. The permitted explicit selections above
retain all other declared common quick Python patterns. Native compilation,
real driver/keyboard/WK/Photos/audio/render semantics, signed installation and
all device/Proxmox tests remain unverified. No dependency was installed.

## Final source preservation check

The original iOS worktree still has HEAD
`f85409d3b4b9c0c1f292b2bb5bbd903c5ff88347`, the same sole modified file and the
same original file SHA-256 recorded above. Its index, files and branch were
never changed by this work. No Phone/Pico/frozen worktree was written, and no
remote resource, protected branch or acceptance record was changed.

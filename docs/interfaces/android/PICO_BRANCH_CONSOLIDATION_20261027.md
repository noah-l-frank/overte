# Pico test branch consolidation: 2026-10-27

The continuation branch is `test/android-pico/consolidated-adapters-20261027` in
`noah-l-frank/overte`. It consolidates the 18 remote branches below.
The starting tree is the reviewed adapter integration at
`3185af80eddb6e952c7c1dca86d25730f35b0dd9`.

Each original tip is an ancestor of the consolidated branch. Normal merge
commits preserve the original histories, including WIP checkpoints. Earlier
agent changes already selected into the reviewed integration retain their newer
implementations, source guards, test partitions, and verification records.
This avoids replacing those corrections with older agent versions.

The Assets picker WIP is represented by the newer integrated acknowledged-open
consumer admission, cold recovery, and no-adoption regressions. The Avatar
memento WIP retains the integrated typed Handle restoration with newer GUI and
monotonic CAS guards. Shared Script restart WIP retains its later owner-aware
recovery and read-only session-absence checks. Older implementations of those
same behaviors remain in the merged history without replacing the newer code.

Additional source changes include the independent canonical Lifecycle Actor
factory and its existing tests, ModelCache admission preparation, the World
lifecycle contract proposal, and the WIP native/Java input-consumption recorder.
The recorder remains work in progress; this consolidation does not declare its
protocol complete or register a new public capability.

No permanent product branch is changed by this consolidation. Historical
coverage and handoff records retain their original branch names and source
identities. Use the consolidated branch for subsequent work.

## Original remote tips

| Original branch | Preserved tip |
| --- | --- |
| `test/android-pico/assets-adapter-wip-20261025` | `691994063b51ff60ca476245b56a5c89e60bfbcd` |
| `test/android-pico/assets-model-material-texture-20261024` | `88723b9b7575271f5fa3aa44ecebbfb20eca725e` |
| `test/android-pico/assets-recovery-wip-20261025` | `fb725c82935ba7c1dd0dd23f4689fbc3c842b799` |
| `test/android-pico/assets-resource-caller-20261024` | `07d742f7139bf9ede1137da2a9bba5efb2f1832b` |
| `test/android-pico/audio-adapter-agent-20261022` | `ca2644ef32b3a6e920026523b4b15e8a57639e94` |
| `test/android-pico/avatar-contacts-agent-20261022` | `8b05d1fa2cec90f19431670b6205b09ace59917e` |
| `test/android-pico/avatar-memento-wip-20261025` | `15641f7e1dbb298693f684cd8402cf754f0c6592` |
| `test/android-pico/avatar-original-persistence-owner-agent-20261024` | `37889154baf075f859a40ba2ab9851ce5bd91fff` |
| `test/android-pico/avatar-peer-source-join-agent-20261024` | `b84d9a780dc44639f8da5d652df1995ffb35174a` |
| `test/android-pico/avatar-typed-memento-cas-agent-20261024` | `948eccff3784b2b022c3aced78c89538c7a61b54` |
| `test/android-pico/chat-adapter-agent-20261022` | `aca7803ef514e4affde9d3eae8f2af7e2aeca195` |
| `test/android-pico/create-adapter-agent-20261022` | `cbcb0a78a7bcaf69ce73e6663f5a0c0f2525f9b3` |
| `test/android-pico/create-source-retirement-20261024` | `2461f0ccb99725544e6d2adb2ddee84373eee766` |
| `test/android-pico/feature-adapters-parallel-20261021` | `3185af80eddb6e952c7c1dca86d25730f35b0dd9` |
| `test/android-pico/lifecycle-adapter-agent-20261022` | `640af90e1c297a897fa755ff1afd8835d8670a16` |
| `test/android-pico/lifecycle-continuation-agent-20261024` | `f8151164f725adfe4ecad0642d11edf1b7efb6e7` |
| `test/android-pico/shared-adapters-wip-20261025` | `5dc668f39fa068ac5d0455bfce9cd0bb3c0ccbd1` |
| `test/android-pico/world-document-wip-20261025` | `1d71829901e1fccb3a7d3addfef4ebe570085443` |

No archive tags are needed: all original tips remain reachable through the
consolidated remote branch. The old refs may be removed only after verifying
that the published branch contains these exact tips and that the old refs
still point to the recorded commits. Deletion uses exact expected-tip leases.

## Verification

The following checks pass on the consolidated tree:

- Ancestry checks for all 18 original tips.
- Python syntax parsing for every changed Python source.
- `python3 tests/device/validate_contract_versions.py`.
- `python3 android/vr/pico/tests/pico4-coverage-test.py` (15 tests; all 14 risk areas).
- `python3 android/vr/pico/tests/pico4-test-suite-self-test.py` (12 tests).
- `python3 android/vr/pico/tests/device/test_lifecycle_actor_factory.py` (4 tests).
- `python3 android/vr/pico/tests/device/test_world_current_input_java.py` (1 test).
- `python3 android/vr/pico/tests/device/test_world_current_document_java.py` (1 test).
- `python3 android/vr/pico/tests/device/test_world_current_input_reader.py` (16 tests).
- `python3 android/vr/pico/tests/device/test_world_current_document_reader.py` (9 tests).
- Direct generation of all four original ModelCache admission fragments and
  their source provenance in a temporary directory.
- `python3 tests/check-documentation.py --all` (758 Markdown files).
- `git diff --check 3185af80eddb6e952c7c1dca86d25730f35b0dd9 HEAD`.

General repository verification uses the command documented in this branch:
`python3 tests/run-project-tests.py --profile quick --timeout 240`.
It finishes with **57 passed and 2 failed groups** in 1,015.46 seconds:

- `device-e2e-contracts` reaches its outer 240-second limit. Its JUnit records
  interruption by signal 15 while `python-pico-lifecycle-pending` is running;
  the inner test output reports no assertion failure before interruption.
- `pico4-device-free` reaches the same outer limit while the compiled Chat
  dispatcher selection is still running.

Both interrupted test source files are unchanged from the starting tree.
These timeouts are not passing full-suite evidence; no complete baseline
comparison or timeout-policy change is claimed. The newer main-branch
`tests/pr-ci-*-test.py` commands are unavailable on this historical product tree
and are not presented as executed checks.

No complete native application/APK build or physical-device test is part of
this consolidation. Existing source/host verification does not qualify a
device or complete the remaining feature work.

# iOS test branch consolidation: 2026-10-27

The continuation branch is `test/ios/consolidated-adapters-20261027` in
`noah-l-frank/overte`. It consolidates all four original remote
`test/ios/*` branches below.

The starting tree is the most complete WIP checkpoint,
`0411fbfd6fd57cc249dc2c34829f7f8521ac8a1b`.
After merging the remaining histories, its complete source tree is unchanged.
Only this consolidation record and the README continuation pointer are added.

## Preserved histories and conflict resolution

| Original remote branch | Preserved tip |
| --- | --- |
| `test/ios/feature-adapters-wip-20261025` | `0411fbfd6fd57cc249dc2c34829f7f8521ac8a1b` |
| `test/ios/parity-fixture-verification-20261018` | `824576556959ac75c8ebdb137062b55c808d6994` |
| `test/ios/parity-snapshot-automation-20261019` | `7684f23884fffbcd4007887d0329f35c18fccbb9` |
| `test/ios/shared-adapters-wip-20261025` | `6f7307ff4038cc9efb5a9b26f0446e7a32e6d429` |

The snapshot-automation tip was already an ancestor of both WIP branches.
Two normal merge commits retain the shared-adapter and parity-verification
histories. All four exact original tips are ancestors of the consolidation.

The shared-adapter WIP's earlier installed-code recovery implementation is
already superseded by the starting tree's version 4. The merge retains its
newer recovery proofs, legacy version readers, native-clock validation, and
durable ownership checks. The earlier parity-verification changes are likewise
present with later historical-certificate and protected-policy regressions.
Their older implementations remain recoverable through merge ancestry.

All WIP, including the feature-adapter checkpoint's uncompleted work, remains
in the consolidated source and history. This operation changes no permanent
product branch and makes no feature-completion claim. Historical source and
branch identities in older handoff records remain unchanged.

## Verification

The following checks pass on the consolidated tree:

- Ancestry checks for all four original remote tips.
- `git diff --exit-code 0411fbfd6fd57cc249dc2c34829f7f8521ac8a1b 4eb5857dcb`
  confirms that history integration changes no file content.
- Python syntax parsing for every tracked `tests/device/ios/**/*.py` source.
- `python3 tests/device/ios/self_tests/test_ios_installed_code.py` (15 tests).
- `python3 tests/device/ios/self_tests/test_ios_launch_recovery.py` (21 tests).
- `python3 tests/device/validate_contract_versions.py`.
- `python3 tests/check-documentation.py --all` (760 Markdown files).
- `git diff --check 0411fbfd6fd57cc249dc2c34829f7f8521ac8a1b HEAD`.

General repository verification uses the command documented in this branch:
`python3 tests/run-project-tests.py --profile quick --timeout 240`.
It finishes with **45 passed and 1 failed group** in 761.39 seconds.
The `device-e2e-contracts` group reaches its outer 240-second limit. Its inner
JUnit records two failed groups:

- `python-native-feature-bound-clock` cannot import `adapters` because its
  invocation lacks the device package path.
- `python-graphics-resources` is interrupted by signal 15 when the outer
  timeout expires.

The affected test and runner files are unchanged from the original WIP tree.
The exact bounded diagnostic command
`PYTHONPATH=tests/device python3 -m unittest discover -s tests/device/self_tests -p test_native_feature_bound_clock.py`
passes all 12 clock tests. This verifies the test with its import path supplied;
it does not repair the existing full-runner invocation or turn the incomplete
overall E2E run into passing evidence. No timeout policy is changed.
The newer `tests/pr-ci-*-test.py` commands on main are not part of this
historical tree.

Before deleting the original remote refs, verify the published consolidation
contains all four exact tips and that each old ref still points to its recorded
commit. Use expected-tip leases and atomic deletion; no archive tags are needed.

No IPA build, simulator, installation, or physical-device test is performed.
Existing source and host evidence does not qualify a device or complete the
remaining product work.

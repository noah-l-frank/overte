# Local feature-journey validation

Validated on the isolated local branch
`test/main/shared-feature-journeys-20261019`, based on the shared Main parity
source `7636452f2124029798948aafae70ecff5c5fa7d0`. All changes are under
`tests/device`. No product source, production adapter, global CI workflow,
acceptance policy or physical evidence was changed.

## Results

- 230 device-free Python self-tests passed, including 26 feature-journey tests,
  15 Create management tests and 16 Scripts management tests. Individual methods
  additionally exercise all fourteen areas and many fault-injection subcases.
- The ordinary runner was tested with the deterministic virtual adapter: a
  missing mandatory feature capability makes the result fail without
  `--require-complete`. A separate test checks missing reused foundation
  capabilities. No physical target was discovered or contacted.
- The new resource check validated 28 hash-pinned repository/companion resources.
  The existing fixture check validated its six controlled entities.
- Contract-version, acceptance-policy, catalog/profile composition, documentation
  and whitespace checks passed. The policy still has no physical acceptance gates
  or registered evidence promoted by this work.

The quick Python groups were selected from the existing
`run_control_plane_tests.commands('quick')` inventory. Exactly three existing
voice native compiler tests were deliberately omitted to honor the explicit
no-build scope. They were not replaced with simulated passes:

- `test_actual_clock_survives_input_shutdown_and_cancels_on_lifecycle_loss`
- `test_actual_cpp_generator_matches_python_reference_and_reset`
- `test_actual_qt_hook_compiles_and_bounds_recording_lifecycle`

The full project quick profile and full prepared-host/device profiles were not
run, because they include compiler/build or device requirements outside the
request. No SDK installation, application build, device access, Jenkins job,
Appium/device-connect service, GitHub write, push or integration occurred.
Loopback fixture tests started only short-lived Python resource/journal servers
and joined/shut down their own threads.

## Commands and reproduction

The focused implementation packages were verified with:

```bash
python3 -m unittest discover -s tests/device/self_tests -p test_feature_journeys.py -v
python3 -m unittest discover -s tests/device/self_tests -p test_create_management.py -v
python3 -m unittest discover -s tests/device/self_tests -p test_scripts_management.py -v
python3 tests/device/feature_journeys/server.py --check
python3 tests/device/fixture/serve.py --check
python3 tests/device/validate_contract_versions.py
python3 tests/device/validate_policy.py --policy tests/device/acceptance-policy.json --catalog tests/device/catalog.json
python3 tests/run-project-tests.py --suite documentation --timeout 240
git diff --check
```

The broader no-build selection was executed by a local validation script outside
the checkout. This equivalent selection reproduces the same group membership
from the repository root at this source revision; it adds no runner flag or CI
skip path:

```bash
python3 - <<'PY'
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path('tests/device').resolve()))
import run_control_plane_tests
omit = {
    'test_actual_clock_survives_input_shutdown_and_cancels_on_lifecycle_loss',
    'test_actual_cpp_generator_matches_python_reference_and_reset',
    'test_actual_qt_hook_compiles_and_bounds_recording_lifecycle',
}
def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test
selected = []
for name, command, qml in run_control_plane_tests.commands('quick'):
    if '--pattern' not in command:
        continue
    pattern = command[command.index('--pattern') + 1]
    suite = unittest.defaultTestLoader.discover('tests/device/self_tests', pattern=pattern)
    selected.extend(test for test in flatten(suite)
                    if getattr(test, '_testMethodName', None) not in omit)
result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(selected))
raise SystemExit(0 if result.wasSuccessful() else 1)
PY
```

## Meaning of the result

**Test logic exists. Adapters are missing. Device behavior is untested.**
The boundary model independently reduces input verbs and supplies simulated
product/actor observations. Assertions never receive scenario checkpoints as
measurements. Counterexamples cover ignored input, product-only forged success,
foreign/stale/frozen observations, missing/malformed bytes, silent or foreign
PCM, wrong export geometry/source, wrong asset bytes, missing companions,
stalled script effects, missing Sit variants, unexpected process/lifecycle
changes, early actor samples and incomplete cleanup. The result verifies those
common assertions and orchestration decisions, not Overte product behavior.

Later hardware qualification must use the Proxmox Jenkins laboratory and the
normal installed-code identity, privacy and acceptance procedures. The retired
workstation device laboratory must remain disabled. The concrete source and
measurement obligations are in the [adapter handoff](FEATURE_ADAPTER_HANDOFF.md).

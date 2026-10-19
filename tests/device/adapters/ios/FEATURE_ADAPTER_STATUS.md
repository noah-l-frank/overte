# iOS feature adapter implementation status

Branch: `test/ios/shared-feature-adapters-20261019`.
Product base: `864f8b79a4`, composed with Main's shared journeys/observation
helpers through local parent-to-child merges. Neither Phone nor Pico history
was merged into iOS. No build, signing, installation, device access or protected
integration was performed.

The existing iOS native component now has an internal `_feature_observer` and
`ios/adapters/feature_observation.py` (under `tests/device`). It uses the real
native process observer, the existing owned fixture command endpoint and AFC
Documents `mobile: pullFile` transport. It never sets product state. One closed
read-only request obtains actual `ScriptDiscoveryService` rows and optionally
actual avatar-owned entity IDs from the shared probe.

The reader validates the selected physical iOS component profile, safe bundle/
Documents paths, exact HTTP echo, original bounded base64/JSON bytes, current
request ID, actual advancing source sequence/capture timestamp, unchanged probe
instance and live foreground bundle/PID before and after capture. Redirects are
refused. Missing, partial, stale, foreign, incomplete or oversized documents
cannot become accepted state. Temporary AFC missing-file responses may be
polled within five seconds/51 reads; native errors stay private. Expected values
are never sent or substituted. No `feature.*` capability is advertised.

**Canonical execution remains blocked.**
`tests/device/adapters/ios/binding.py::create_adapter` deliberately omits
`executionIdentity` from descriptions, refuses sessions/invocations and now
explicitly refuses `_feature_observer` too. Its unchanged reason is
`OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE`. The offline candidate/IPA verifier,
bundle ID, PID, prior installation receipt and self-reported probe source cannot
establish the independently reviewed installed-code/signature association.
This new component must never be used to bypass that gate.

Concrete native input blocker after that prerequisite:
`tests/device/ios/adapters/normal_input.py::CONTROLS` and the actual E2E-only
`IOSNormalUiInput` producer currently cover HUD/address, Places/history and SNAP.
They do not expose Create fields/history/entity selection, full-URL script
rows/dialogs, assets or their cancellation/ownership observations. General
UIKit accessibility existence is not proof of the same native controls. The
next packet needs source-reviewed ordinary Qt pointer/IME mappings and actual
control tokens on those live roots, with stale context and cleanup handling.
No product/target-automation code was changed under the current scope.

The larger fourteen-area v1 contracts additionally need native lifecycle event
counters, complete product state readers, an independent real account/domain/
peer actor and original render/PCM/recording/export/share/upload evidence.
All fourteen remain **common test logic present; full adapter missing; devices
untested**. Existing component navigation and Snapshot implementations remain
unchanged and are not installed-code/device acceptance.

Hardware-free checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/device/ios/self_tests -p test_ios_feature_observation.py
PYTHONDONTWRITEBYTECODE=1 python3 ios/tests/appium-native-binding-test.py
```

The new eight-case file is discovered by the existing
`ios/tests/run-tests.sh` Python self-test group. No global workflow was changed.
Tests replace HTTP/AFC/process/time boundaries and use one owned loopback server
to verify redirect refusal. That server is a protocol fixture, not an Appium or
device laboratory. Original binding tests also prove that a successful candidate
preflight still cannot invoke this reader through the bound adapter. These are
adapter control-logic checks only. Future hardware qualification belongs
exclusively to the Proxmox Jenkins lab.

# Pico 4 CI/CD

This personal hobby fork separates device-free checks from trusted builds and
hardware tests. Its self-hosted build runners and private Proxmox Jenkins
laboratory are the maintainer's own infrastructure, not public contributor
services. Local host checks do not require access to them.

## Device-free pull-request CI

The central selective PR controller in `repository-checks.yml` reports
`source-policy` and `required-ci`. It selects shared and branch-owned consumers
from their actual inputs. The [selective CI guide](https://github.com/noah-l-frank/overte/blob/main/docs/PR_CI.md)
owns the current acceptance contract; retained project-runner and synchronization
recipes describe earlier implementations, not additional current required
contexts. Actions was disabled when inspected on October 22, 2026. Local
qualification and an installed workflow do not establish hosted execution.

The shared execution runs on GitHub-hosted Ubuntu, uses read-only repository
permissions, does not persist checkout credentials, and pins third-party actions
to immutable commits. Host reports have explicit seven-day retention. Separate
Android platform push/manual checks are in `android-vr-tests.yml`, named
`Android VR integration tests`. Neither these host checks nor the trusted APK
build connects to a headset or invokes ADB.

## Trusted Pico build

`.github/workflows/pico4-build.yml` is manual-only. It executes repository code
on a runner carrying all of these labels:

```text
self-hosted, linux, x64, overte-android-build
```

Treat that label as a security boundary. Assign it only to an isolated runner
dedicated to trusted Overte Android builds. Do not add a pull-request trigger:
unreviewed code must never execute on this host. Prefer an ephemeral runner;
otherwise remove the checkout and build directories after each job and do not
place unrelated credentials, signing material, or device access on the host.
The workflow also rejects every source ref except `android-vr-pico` and
immutable `pico4-preview-N` tags.

Provision the runner by following `android/vr/pico/docs/BUILD.md`, then verify it from
the repository root:

```bash
android/vr/pico/build.sh doctor
```

Supply the four explicit environment values and complete source graph described
in [SOURCE_INPUTS.md](../release/SOURCE_INPUTS.md), then run:

```bash
android/vr/pico/build.sh deps --source-graph
android/vr/pico/build.sh prepare
```

The checked-in debug and release workflows still invoke the legacy
`deps --download` helper before preparation. Those checksum-verified downloads
do not satisfy the current source-input consumer. The workflows do not declare
the four source-input values themselves; a selected trusted runner would need
the correct explicit inputs independently. Their presence in the repository
therefore does not establish a working current native build or release lane.
Read the actual run and source-input bindings before interpreting its result.

The workflow is designed to run device-free tests before compiling, build the
debug APK, and reject output with an unexpected package, SDK contract, ABI, native
library set, ZIP structure, or signature. Its JSON manifest records the exact
Git revision and APK SHA-256 digest. Only that small manifest and the JUnit
report are uploaded to Actions storage for seven days. The roughly 550 MB APK
is deliberately not uploaded as an ordinary workflow artifact.

## Release-candidate stage

`.github/workflows/pico4-release-candidate.yml` is the manual-only second
stage. Dispatch it from an existing tag named
`pico4-vMAJOR.MINOR.PATCH-rc.N`, for example `pico4-v1.4.0-rc.2`. Mutable
branches, preview tags, final-version tags, tag/ref mismatches and RC zero are
rejected. Minor and patch are limited to 0..99 and RC to 1..99. The tag derives
both Android values without an independent input:

```text
versionName = MAJOR.MINOR.PATCH-rc.N
versionCode = MAJOR*10000000 + MINOR*100000 + PATCH*1000 + N
```

The APK verifier compares both values, the exact source commit and the release
certificate SHA-256 fingerprint after signing. The workflow produces canonical
JSON provenance, a dependency-bundle CycloneDX SBOM and sorted SHA-256 manifest.
This SBOM is an initial supply-chain inventory, not a claim that every native
or Java transitive component has been enumerated. `SHA256SUMS` is also the
subject list intended for a later GitHub artifact-attestation step; attestation
is deliberately not enabled until organization policy and OIDC trust are
configured.

The only network-side result is a **draft** GitHub release with verified files.
The workflow contains no publish operation. Re-running for a tag with an
existing release fails instead of replacing assets.

### Protected environment and secrets

Create an environment named `pico4-release-candidate`, require selected release
maintainers as reviewers, prevent self-review where supported, restrict it to
protected Pico RC tags, and store only these environment secrets:

- `PICO_RELEASE_KEYSTORE_BASE64`: base64 of the dedicated Android keystore;
- `PICO_RELEASE_STORE_PASSWORD`, `PICO_RELEASE_KEY_ALIAS`, and
  `PICO_RELEASE_KEY_PASSWORD`;
- `PICO_RELEASE_CERT_SHA256`: lowercase 64-hex certificate fingerprint.

Do not create repository-level copies. The temporary keystore is mode-restricted
and removed in an always-running cleanup step. Rotate the key through a reviewed
environment change and update the expected fingerprint at the same time.

### Runner provisioning

The release runner requires labels `self-hosted, linux, x64,
overte-android-release`, the toolchain from `PICO4_BUILD.md`, `base64`, and the
GitHub CLI authenticated only through the job token. It must be isolated from
pull-request runners and devices, preferably ephemeral, have no ambient cloud
or repository credentials, and start from an empty build directory. Pin the
runner image/tool versions administratively and retain its inventory with each
candidate. Never assign `overte-android-release` to a general build host.

### Separate device-acceptance implementation

The maintainer's hardware tests run through their private Proxmox Jenkins
laboratory, using the prepared `overte-jenkins` wrapper. The former workstation
device laboratory was retired on October 19, 2026 and is not a fallback. See
the [shared operator guide](https://github.com/noah-l-frank/overte/blob/main/docs/portal/jenkins/index.md)
for that personal deployment boundary.

`.github/workflows/pico4-device-acceptance.yml` retains a separate,
manual approval-gated implementation. Its presence is not evidence that its
environment or device runner is deployed. It is not the entry point for the
maintainer's current laboratory. Its default inspection job runs on a
GitHub-hosted runner, consumes the APK digest from `SHA256SUMS`, validates the
draft release, tag, commit and APK manifest, and cannot invoke ADB. It neither
rebuilds nor publishes the candidate.

Device access is skipped unless `execute_device_install` is explicitly enabled
and `confirmation` exactly equals `INSTALL <selected-tag>`. That job requires
the protected `pico4-device-acceptance` environment and runner labels
`self-hosted, linux, x64, overte-pico4-device`. On the device runner it
redownloads the draft assets, re-verifies package identity, versions and the
certificate fingerprint with `PICO_RELEASE_CERT_SHA256`, verifies the digest,
takes the repository-wide device lock, requires exactly one authorized USB
Pico, installs with `adb install -r`, and performs a minimal launch smoke test.
The report binds the result to tag, commit and APK digest. It never rebuilds or
publishes. The RC workflow itself remains ADB-free.

A separately reviewed deployment of this implementation would need a
`pico4-device-acceptance` environment separate from signing, required reviewers,
protected RC-tag restrictions, and only `PICO_RELEASE_CERT_SHA256`. The device
runner would not need the keystore or its passwords. Such a deployment must
keep the runner isolated with one authorized Pico and no ambient credentials.
Those prerequisites are not provisioned by a clone of this hobby fork and are
separate from the maintainer's current Jenkins deployment.

Running only the non-mutating local contract is safe without a headset:

```bash
android/vr/pico/ci/pico4-device-acceptance.sh \
  --tag pico4-v1.2.3-rc.4 --revision <40-hex-commit> \
  --apk picoInterface-release.apk --checksums SHA256SUMS \
  --apk-manifest apk-manifest.json --output device-acceptance-plan.json
```

Never pass `--execute` outside the protected workflow unless device mutation
has been separately authorized.

### Required checks and repository administration

The live `android-vr-pico` rules were inspected on **October 22, 2026**. They
require `source-policy`, `required-ci`, and
`Enforce Android parent sync path`, with strict up-to-date validation and
GitHub Actions integration binding. The old
`Pico 4 device-free CI / project-tests` check is not a current required context.
The [shared CI overview](https://github.com/noah-l-frank/overte/blob/main/docs/portal/testing/github-actions.md)
explains the corresponding owners and how to read back live branch rules.
This is a dated observation, not an instruction to change repository settings.

Pico RC tags use their own versioned protection policy; inspect its live rules
before a release operation. GitHub cannot require a workflow check before
creating a tag, so create one only from a reviewed commit whose applicable
checks passed.
The environment approval and `Pico 4 release candidate / release-candidate`
job are release gates, not merge checks. Do not make the manual release job a
required branch check because ordinary pull requests cannot trigger it.

Android Phone CI should reuse the same separation and contract-testing pattern
on its own product branch. It must define its own package, ABI, native-library,
version, signing, and artifact-size contracts rather than importing Pico values.

Store, third-party distribution and direct-install readiness are tracked in
`android/vr/pico/docs/PICO4_DISTRIBUTION_READINESS.md`. Those requirements are partly
portal- and policy-dependent and are deliberately not represented as a passed
CI gate.

## Local contract checks

Run the workflow and APK-verifier regressions without Actions or an Android
device:

```bash
python3 tests/workflow-contract-test.py
python3 android/vr/pico/tests/pico-apk-verifier-test.py
```

These checks prevent permission expansion, mutable action references,
credential persistence, untrusted self-hosted execution, accidental large APK
artifact uploads, and weakening of the Pico APK identity checks.

# Build the Overte client for Pico 4

> [!CAUTION]
> **AI-assisted experimental Pico 4 port**
>
> This Pico 4 port is developed with the assistance of AI tools. Its code and
> build workflow are experimental and may contain incomplete, poorly tested,
> insecure, or otherwise dangerous changes, including quick-and-dirty fixes.
> Review everything carefully and do not treat this port as production-ready.
>
> This work is maintained separately in a fork in respect of Overte's
> [no-AI-contributions policy](https://github.com/overte-org/overte/blob/master/CONTRIBUTING.md).
> For the official, stable project, use the
> [original Overte repository](https://github.com/overte-org/overte). See the
> fork's [full AI-use disclaimer](../../../../README.md) for more information.

The Pico 4 client has a maintained command-line build workflow for 64-bit
Linux. Run all commands below from the repository's `android/vr/pico/` directory.

Local source builds do not require the maintainer's private device laboratory.
Hardware, installation, power, and microphone commands below are references for
a prepared test agent or an independent lab. The maintainer uses private Proxmox
Jenkins jobs; the workstation lab is retired. See the
[operator guide](https://github.com/noah-l-frank/overte/blob/main/docs/portal/jenkins/index.md).
Some helper messages retain the historical `build-pico.sh` name; the executable
in this source tree is `android/vr/pico/build.sh`.

## Bootstrap distribution handlers

| Operating system | Bootstrap handler |
| --- | --- |
| Fedora Linux 44 | Present |
| Ubuntu 24.04 | Present |
| openSUSE Tumbleweed | Present |
| Arch Linux | Present |
| Debian 13 | Present |

These handlers describe package-manager setup coverage, not a new full-build
or physical-device qualification on every listed distribution.

## Quick start

On a new development machine, inspect and prepare the host toolchain:

```bash
cd android/vr/pico
./build.sh doctor
./build.sh bootstrap
```

The bootstrap supports Fedora, Debian/Ubuntu, Arch Linux, and openSUSE. It may
request administrator access for missing system packages and Android SDK
license acceptance. When the operating system only provides a newer,
incompatible Java version, the bootstrap installs a checksum-verified Eclipse
Temurin 21 JDK locally. If the base Android command-line tools are missing, the
script displays Google's license page, asks for explicit acceptance, and then
downloads and checksum-verifies the current official Linux tools. Android SDK
Platform 36, Build-Tools 36.0.0, the NDK, and ADB are installed afterward with
`sdkmanager`.

Preparation and builds now consume an explicitly supplied, revision-bound
source graph. Follow [Source dependency inputs](#source-dependency-inputs)
before running:

```bash
./build.sh deps --source-graph
./build.sh prepare
./build.sh build
```

These commands do not install onto a headset. With valid inputs already supplied,
`./build.sh` combines preparation and the debug build. Hardware installation
belongs to the [prepared-agent path](#install-and-run-on-a-pico-4).

To measure the completed client's battery and power use on the headset, see
[Measure Overte power use on Pico 4](POWER_TEST.md).

For the device-free pull-request checks and trusted build-runner design, see
[Pico 4 CI/CD](pico4-ci-cd.md).

For world-entry and post-loading optimization measurements, see the
[Pico 4 world-loading guide](world-loading/pico4-optimization-guide.md).

`deploy` also requires those explicit source inputs. It does not produce or
qualify the source dependency graph.

## Requirements and automatic setup

The build requires Conan 2, Git, CMake, Ninja, Python, Perl, Android SDK
Platform 36, Build-Tools 36.0.0, NDK `27.3.13750724`, Platform-Tools/ADB,
util-linux `flock`, and a JDK from version 17 through 21. Android Studio is
optional, but provides the Android SDK and a compatible JDK conveniently.

Inspect the complete environment without changing anything:

```bash
./build.sh doctor
```

Missing requirements are reported together with an official installation page
or an appropriate `sdkmanager` command. The automatic bootstrap variants are:

```bash
./build.sh bootstrap
./build.sh bootstrap --check
./build.sh bootstrap --system-packages
```

- `bootstrap` installs as much of the complete toolchain as possible.
- `--check` is the read-only `doctor` check.
- `--system-packages` only handles packages from the operating system.

The retained `bootstrap --with-deps` and `setup --download` modes use the older
dependency helpers. Their downloads do not satisfy the current source-input
consumer. Use the source-input contract below rather than treating those modes
as a complete current build setup.

## Daily development commands

| Command | Purpose |
| --- | --- |
| `./build.sh` | Prepare existing dependencies and build the debug APK |
| `./build.sh build` | Revalidate source inputs and build the debug APK |
| `./build.sh install` | Install and start an already built APK |
| `./build.sh deploy` | Prepare, build, install, and start the client |
| `./build.sh prepare` | Validate and resolve the explicitly supplied source graph |
| `./build.sh deps --source-graph` | Consume the same explicit source-input contract |
| `./build.sh deps --download` | Retained legacy download helper; not current build inputs |
| `./build.sh --help` | Show commands and supported path overrides |

`PICO_BUILD_JOBS` bounds Gradle, native compilation, and shader generation to
the same host-worker count. `PICO_SHADER_JOBS` can override only shader
generation when memory or shared-runner load requires a lower limit. Use
`./build.sh build --stacktrace` to include Gradle failure details when
diagnosing an unsuccessful CI or local build.

Before building, or on a host without Pico/Android dependencies, run the
device-free regression suite from the repository root:

```bash
./android/vr/pico/tests/pico-device-free-test.sh
```

It performs shell syntax checks and the WebView, microphone, OpenXR lifecycle,
runner-mock, serverless-fixture, device-lock, and power-analyzer regressions. It
does not invoke ADB, connect to a device, download dependencies, or modify
device settings. Native Qt/C++ suites remain available separately through
`android/vr/pico/tests/pico-host-regression-test.sh` when a CMake build is configured.

After a build, verify that the output is a signed, structurally valid Pico APK:

```bash
./ci/verify-pico-apk.py \
  apps/picoInterface/build/outputs/apk/debug/picoInterface-debug.apk \
  --expect-e2e-input-layer \
  --output ../../../build/pico4/apk-manifest.json
```

The verifier fails closed if the package identity, SDK levels, signature,
ARM64-only ABI set, ZIP integrity, or required Pico/OpenXR native libraries do
not match the application contract. It writes the version, size, and SHA-256
digest to a small JSON manifest suitable for CI retention. `aapt` and
`apksigner` must be on `PATH`, or their exact Build-Tools paths can be provided
with `--aapt` and `--apksigner`.
Debug verification requires the E2E-only explicit OpenXR input layer and its
manifest as a pair. Release automation passes `--forbid-e2e-input-layer`, so a
release APK containing either test artifact fails before publication or device
installation.

## Default Pico graphics profile

The Pico Interface uses the measured Pico 4 quality/performance baseline by
default: 80% OpenXR render scale at the runtime's lowest supported refresh rate
(72 Hz on Pico 4), forward rendering, low world detail, and no shadows, bloom,
ambient occlusion, antialiasing, fixed foveation, or statistics overlay. Haze,
local lights, and procedural materials remain enabled because disabling them
did not produce a repeatable benefit.

The render scale can be changed under **Settings > Graphics > Pico render
resolution** and takes effect after the prompted app restart. See
[Pico 4 graphics optimization results](power-tests/pico-graphics-optimization.md)
for the controlled measurements and rejected alternatives.

Restart arguments are stored once in app-private preferences before the old
process exits. The exported launcher cannot accept raw command arguments from
another application, and the internal Qt Activity is not exported.

## Sharing one headset between worktrees

All tracked Pico device runners coordinate through an exclusive lock in the
repository's Git common directory. Linked worktrees share that directory, so a
test in one Codex session makes another session wait before its first ADB
operation instead of changing the app, fan, properties, or scene underneath
the active test.

Check the shared state or wrap an ad-hoc device command explicitly:

```bash
./pico-device-lock.sh status
./pico-device-lock.sh run -- "${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}/platform-tools/adb" devices
```

`status` exits with 1 while the headset is occupied and reports only the holder
PID, start time, and branch. `run` prints that it is waiting, blocks until the
current operation releases the lock, and releases it when its command exits or
is interrupted. Use the wrapper for every manual ADB sequence. The Pico build
installer, power runner, graphics/avatar matrices, simpleperf, unattended
controller, and microphone runner acquire it automatically.

The coordination behavior can be tested without ADB or a headset:

```bash
./tests/pico-device-lock-test.sh
```

## Source dependency inputs

The current `prepare`, `build`, and Gradle paths use the in-tree
`release/pico-source-inputs.py` consumer. It validates supplied inputs; it does
not fetch, build, repair, or certify a dependency graph. The authoritative
[source-input contract](../release/SOURCE_INPUTS.md) defines these environment
values and the supported v1/v2/v3 bindings:

| Variable | Required input |
| --- | --- |
| `PICO_SOURCE_GRAPH_ROOT` | Canonical absolute root of the supplied attempt |
| `PICO_SOURCE_INPUTS` | Regular JSON binding supplied by the input owner |
| `PICO_SOURCE_INPUTS_SHA256` | Independently reviewed SHA-256 of that binding |
| `PICO_EXPECTED_SOURCE_SHA` | Exact application revision matching this checkout and the selected contract |

The input owner must supply the completed phases, original producer receipts,
source closure, package/generator files, host tools, and Qt runtime patch
bindings required by the selected contract. A v2/v3 dependency producer revision
is distinct from the actual current application revision. Retain both identities;
do not relabel an old receipt or generate a replacement digest merely to accept
changed input bytes. Successful input resolution does not establish native APK,
16 KiB, OpenXR, or headset acceptance.

Historical `deps --download` output and the old Conan cache/runtime-overrides
layout are not inputs to this consumer. Their checksum policy remains in
[dependency-releases.json](../../../../.github/dependency-releases.json) for the
retained helper; it does not establish compatibility with the current build.

## Install and run on a Pico 4

Enable developer mode and USB debugging on the headset, connect it over USB,
and accept the authorization prompt inside the headset. Verify the connection
when necessary:

```bash
"${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}/platform-tools/adb" devices
```

The device must appear with the state `device`. If it shows `unauthorized`, put
on the headset and accept the USB debugging prompt before retrying.

Use `./build.sh deploy` to build a new APK before installation, or
`./build.sh install` to reinstall the existing APK without rebuilding it.
Both installation paths preserve existing app data, start the launcher
activity automatically, and verify that the app process remains active.

For reproducible Pico microphone source and fan-noise tests, see
[`pico-microphone.md`](pico-microphone.md). The accompanying
`pico-microphone-test.sh` script restores automatic fan control and stops the
app after each run.

For controller-to-entity debugging, see the
[object interaction architecture and hardware test matrix](pico4-object-interaction.md).

The command expects exactly one authorized ADB device. Select a device
explicitly when several are connected:

```bash
ANDROID_SERIAL=<serial> ./build.sh deploy
```

## Build output

The wrapper builds the `picoInterface` debug variant. Relative to the repository
root, the APK is written to:

```text
android/vr/pico/apps/picoInterface/build/outputs/apk/debug/picoInterface-debug.apk
```

## Troubleshooting

Start with the environment report:

```bash
./build.sh doctor
```

Common issues are:

- Android command-line tools are installed, but SDK Platform 36, Build-Tools
  36.0.0, the exact NDK, or Platform-Tools are missing. Follow the printed
  `sdkmanager` command or rerun `./build.sh bootstrap`.
- Conan was installed but has no default profile. The bootstrap creates it, or
  it can be created manually with `conan profile detect --force`.
- A connected Pico is `unauthorized`. Accept the prompt inside the headset and
  check the device list with the Platform-Tools command shown above.
- Several ADB devices are connected. Set `ANDROID_SERIAL` as shown above.
- Custom installations are not detected. Use `ANDROID_SDK_ROOT`,
  `ANDROID_NDK_HOME`, `JAVA_HOME`, or the `PICO_*` overrides listed by
  `./build.sh --help`.

## Dependency production and historical helpers

Producing or regenerating the native graph is separate from consuming it.
Follow [SOURCE_INPUTS.md](../release/SOURCE_INPUTS.md) and the owning producer's
actual receipts. The current consumer does not patch/rebuild Qt, select the
newest Conan cache entry, or fall back to compatibility archives. The older
download, `setup`, and `prepare-pico-deps.sh` instructions are preserved in the
[historical guide](https://github.com/noah-l-frank/overte/blob/0b63ee87460bf053a9b67ff2f61f9edb696a88ff/android/vr/pico/docs/BUILD.md);
they are not a substitute for the current source-input contract.

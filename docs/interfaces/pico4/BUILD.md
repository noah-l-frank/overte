# Build Overte for Pico 4

The authoritative detailed command reference remains
[`android/vr/pico/docs/BUILD.md`](../../../android/vr/pico/docs/BUILD.md). Run its build
commands from `android/vr/pico/` on a 64-bit Linux host.

Required tools include Conan 2, Git, CMake, Ninja, Python, Perl, the Android SDK
and NDK, a supported JDK, and ADB for physical installation. Preparation and
builds require the explicit, revision-bound source dependency inputs described
in [SOURCE_INPUTS.md](../../../android/vr/pico/release/SOURCE_INPUTS.md).
The old prebuilt downloads are not accepted inputs to the current consumer.

```bash
cd android/vr/pico
./build.sh doctor
```

After supplying the four reviewed `PICO_SOURCE_*` / `PICO_EXPECTED_SOURCE_SHA`
environment values from that contract:

```bash
./build.sh deps --source-graph
./build.sh prepare
./build.sh build
```

Use `PICO_BUILD_JOBS` to bound general compilation and `PICO_SHADER_JOBS` to
bound shader generation independently. The script's `--help` output is the
authority for supported commands and path overrides.

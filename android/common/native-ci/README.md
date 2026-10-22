# Parent-owned Android native acceptance

`OVERTE_ANDROID_COMMON_NATIVE=ON` selects a production CMake entry point for
`android-main` and `android-vr`. It builds the real Android `interface` shared
library, its shared-library dependency closure, generated entities, shaders and
Qt resources, and the Android parent's common JNI providers. It does not select
a Phone, Pico or Quest application wrapper, Gradle graph or APK. Product child
branches retain their separate application and variant acceptance.

The consumer must provide an authenticated candidate checkout, a fresh external
build directory, the qualified Android arm64-v8a/API-26 dependency graph, the
pinned Android toolchain and prepared host tools. This entry point uses the
existing neutral Android bootstrap unchanged. It does not resolve dependencies,
download artifacts, repair a graph, use legacy precompiled fallback locations or
publish caches. Configure it with the independently verified toolchain and its
actual prepared generator paths; do not substitute a different Conan graph.

`target.conanfile.py` and `android-arm64-ci` declare the Android parent's new CI
dependency intent explicitly. They pin the selected Qt/OpenEXR cohort and the
Node/ETC/WebRTC build variants; they do not inherit an unowned Phone snapshot.
The old product profiles are unchanged. An original qualified Phone producer can
supply matching packages only when exact recipe/settings/options/package/edge
identity and original Build provenance pass independently. Its qualification is
not renamed as parent or Pico qualification. Before compilation the executing
consumer must compare the runtime descriptor against `dependency_intent()` from
`verify.py`, which binds the owning candidate's root/common recipes, dedicated CI
profile/recipe, Qt patch and neutral bootstrap/toolchain. A changed declaration
invalidates that runtime; unchanged package names alone never establish reuse.

Before configuration, request the CMake codemodel:

```sh
python3 android/common/native-ci/verify.py --query --build "$BUILD_DIR"
```

Add these options to the verified toolchain's normal CMake configuration:

```text
-DANDROID=ON
-DOVERTE_ANDROID_COMMON_NATIVE=ON
-DANDROID_ABI=arm64-v8a
-DHIFI_ANDROID_CONAN_GENERATORS=<verified-target-generators>
-DHIFI_ANDROID_HOST_TOOLS=<verified-host-tools>
-DCMAKE_BUILD_TYPE=RelWithDebInfo
-DCMAKE_EXPORT_COMPILE_COMMANDS=ON
-DOVERTE_ANDROID_CI_MOC=<verified-Linux-moc>
-DOVERTE_ANDROID_CI_RCC=<verified-Linux-rcc>
-DOVERTE_ANDROID_CI_UIC=<verified-Linux-uic>
-DOVERTE_ANDROID_CI_QMAKE=<verified-Linux-qmake>
```

The caller may instead use the qualified source graph's existing
`OVERTE_FDROID_CONAN_DIR` host mapping. This changes neither source ownership nor
the independent graph authentication requirement. Do not set a product
`HIFI_ANDROID_APP`; the entry point selects the neutral `commonNative` identity.

Build target `overte-android-common-native`. Every produced shared library uses
`--no-undefined`. After the build exits successfully, run:

```sh
python3 android/common/native-ci/verify.py \
  --source "$CANDIDATE_DIR" --build "$BUILD_DIR" \
  --expected-head "$AUTHENTICATED_CANDIDATE_SHA" --receipt "$RECEIPT"
```

Output verification requires real production targets and compiled sources,
rejects product-child source directories and untracked or changed candidate
translation units, and checks every produced shared library for AArch64 ELF64
identity and 16 KiB LOAD-segment alignment. A configure-only run, empty wrapper,
missing output, host binary, stale codemodel or mismatched candidate fails.
Generated translation units remain build outputs; provenance of their generators
and the complete runtime/dependency inputs belongs to the authenticated executing
consumer and final CI gate. This receipt alone is not authority to reuse a result.
It does not claim APK packaging, executed native unit tests or device coverage.

Run focused contract/negative tests with:

```sh
python3 android/common/native-ci/tests.py
```

Those small CMake fixtures check graph construction and verifier rejection. They
do not qualify a real Android build. Initial qualification must compile/link the
actual candidate with the verified graph and record that separate build result.

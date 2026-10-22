# Pico CI unsigned-release dependency contract

This is a new, Pico-owned CI input contract. Existing source-inputs V1/V2/V3,
manual development profiles, signing and device entry points remain unchanged.
The parent-owned `android/common/native-ci` dependency intent must be integrated
first. `target.conanfile.py` extends that explicit CI recipe, not a stale Phone
source snapshot. The new target profile deliberately selects Node `Release`,
ETC2 `RelWithDebInfo` and WebRTC `Release` in the otherwise `Debug` dependency
cohort for an unsigned `RelWithDebInfo` application. These are declared choices
for this consumer; they do not prove binary or graph equivalence.

The OpenXR-specific non-legacy CMake overlay preserves the 16 KiB linker flags.
Its presence alone does not prove a package was built with those flags. The
consuming runtime must bind the owning CI profile/recipe/adapter and OpenXR
configuration bytes, original producer inputs, exact resolved graph and package
inventory. Changed dependency declarations must reject a stale runtime before
compilation.

`graph_contract.py` supplies bounded compatibility/delta planning helpers:

- `validate_pico_target(nodes)` validates the explicitly selected ABI/API,
  compiler, build-type cohort, Qt recipe/options and OpenSSL/OpenEXR versions.
- `minimum_delta(wanted, origins)` compares complete recipe revision, package
  ID/revision, settings, options, context and dependency-edge DAG identities.
  Every reused package needs a completed original `Build` and complete recursive
  Build lineage. Cache, Skip, inventory transport or an incomplete producer does
  not create Build evidence. A missing cached-package proof rejects the plan;
  it does not silently authorize an expensive rebuild. An unmatched Qt or Linux
  host-tool graph also rejects the plan rather than starting a second full build.
- Linux host/build role mapping is disabled by default. The executing consumer
  may request it only after independently verifying the exact profile and native
  host-package identities; Android settings and roles are never normalized.

Origin dictionaries are an internal interface to an independently authenticated
producer loader. Their digest/status fields are required metadata, not proof by
themselves. The executing consumer must check pinned original graph/completion
receipt bytes, successful invocation and source/toolchain provenance, and the
complete package byte/mode/symlink inventory before calling these helpers. Do not
load caller-provided origin JSON and mistake its self-declared fields for trust.
The actual producer continuation schema is integrated only after it exists.

The result is always
`PICO_CI_DELTA_PLAN_NATIVE_AND_APK_VERIFICATION_PENDING`; it never grants Pico
native or APK acceptance. A Phone dependency producer keeps its original
qualification and source identity. Further required evidence includes:

1. Original Build lineage and unchanged package bytes for every reused node;
   a real bounded build and receipt for genuinely distinct nodes/closure.
2. The intended OpenXR input configuration and actual Android OpenXR ELF outputs
   with 16 KiB LOAD alignment.
3. Actual Pico application and OpenXR plugin compilation/link, unsigned release
   APK assembly, and native output/contents/SONAME/NEEDED/alignment verification.
4. Exact candidate and independently pinned runtime/dependency receipts joined
   into the authenticated required-CI gate. No device result is implied.

Run the offline helper/negative regressions with:

```sh
python3 android/vr/pico/native-ci/tests.py
```

These tests use synthetic graph fixtures and do not resolve Conan dependencies,
build Qt, produce an APK or qualify a hosted runner. The existing Gradle adapter
has intentionally not been switched to this pending contract. It must remain
unusable for acceptance until the real producer proof and runtime are available.

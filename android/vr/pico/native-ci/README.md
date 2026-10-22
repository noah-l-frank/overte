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
build Qt, produce an APK or qualify a hosted runner.

## Immutable runtime consumer

An explicit unsigned Release Gradle invocation with `PICO_CI_INPUTS_SHA256`
selects the new `source-inputs.groovy` / `inputs.py` consumer. Without that variable
the existing V1/V2/V3 consumer remains selected. The new path requires the pinned
map at `/qualification/product-inputs-pico.json`, independently verified original
completion/package-origin/target-graph proof references, and the immutable runtime
inventory under the separate `/qualification` proof mount. References declare
fixed kinds; these describe what the protected publisher must authenticate, not
self-declared proof of completion.

The dependency payload is mounted read-only at both `/prepared` and `/attempt`;
the exact candidate overlays `/attempt/source`. Every selected canonical runtime
file must match the frozen inventory and the same underlying unshadowed file at
`/prepared`. Writable candidate paths, changed declarations, missing proof/tool
identities, incomplete target graphs, Qt/Draco/shader-package mismatches,
unbound runtime selections, legacy OpenSSL and incorrectly aligned OpenXR fail
before native compilation. `PICO_EXPECTED_SOURCE_SHA` binds the candidate HEAD;
it is deliberately independent of the original dependency producer revision.

Use direct offline Gradle invocation with the pinned common wrapper/settings,
`--offline --no-daemon`, `-PPICO_UNSIGNED=1` and explicit
`:picoInterface:assembleRelease`. The legacy `build.sh` invokes its legacy source
consumer before Gradle and is not the new CI entry point. This new consumer never
installs/resolves/repairs dependencies. A separate preflight-admitted producer
must build any distinct OpenXR node before the runtime is frozen.

The map also pins the unchanged original `host_tools_graph` and a
`host_package_bindings` table keyed by exact `ref#RREV:PID#PREV`. The protected
publisher authenticates each restored alias against the original Build and
strong package inventory. Selected target tools must match that original Linux
x86_64 Build identity, settings and options. Conan's raw target graph retains
its null tool paths and Cache/Skip decisions; these never become Build evidence.

After the actual build, `verify_apk.py` verifies the bounded unsigned archive,
required Pico/OpenXR/Interface outputs, no E2E payload, actual ELF64/AArch64/16 KiB
LOAD segments, filename/SONAME equality and the complete packaged DT_NEEDED closure
against explicit Android platform libraries. It checks actual v1 signature
entries and the APK v2/v3 signing-block location. Package/version/API/release
identity and packaged network policy use the existing signed verifier's bounded
helpers without weakening or changing its signing requirements. The resulting
APK digest and actual candidate SHA/tree still require the trusted outer consumer
to join the successful native invocation and independently qualified runtime
provenance. No device coverage is implied.

The executing controller stages the verifier and its supporting helper/policy
files in their reviewed repository-relative layout under a separately pinned
read-only controller root. Pass `--source /attempt/source` to bind the actual
candidate checkout independently of that code location. The candidate manifest
and Git identity come from that checkout; acceptance code and the approved
network-capability policy come from the controller. Running candidate-editable
acceptance code alone does not authorize a passing result.

Additional focused tests:

```sh
python3 android/vr/pico/native-ci/inputs_test.py
python3 android/vr/pico/native-ci/verify_apk_test.py
```

No real Android/APK qualification is claimed by these fixtures. Until an actual
completed producer, protected map and successful candidate build exist, the new
consumer remains unusable for acceptance.

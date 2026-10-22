# Selective platform and browser acceptance

The central planner selects browser journeys only when source, renderer, UI,
browser-test or browser-build code changes in that exact browser project.
Package manifests/lockfiles alone retain their package, security, JavaScript
build and unit-test checks. They do not request a browser or native application.

The gateway browser owner runs the existing Playwright browser suite. The direct
browser owner runs its production distribution in a real software-rendered
browser: WebGL2 initialization, six tablet applications, an actual graphics
slider callback and the disconnected microphone restriction. This bounded
standalone journey does not claim native peer, voice interoperability or device
acceptance. Those existing diagnostic journeys retain their separate owners.
The controller prepares the browser outside the candidate and executes journeys
in an offline container with private loopback, no GPU/device mounts and no host
credentials. The explicit isolated-container flag disables only Chrome's nested
sandbox; the outer container security and network boundary remain enabled.

## Android Java and resources

Relevant production Java, resource and manifest edits select the owning source
compile tier: `common` on `android-main`/`android-vr`, `phone` on `android-phone`,
and `pico` on `android-vr-pico`. Directory presence does not assign ownership;
parent/other-product trees contain legacy product snapshots that must not be
treated as an additional current application.
A product Java/resource exemption applies only on its governed target. Changes
to another product's legacy snapshot cannot borrow the current target's compiler
receipt. Shared Java/resources remain eligible on all Android targets.

The trusted compiler runs AAPT2 36.0.0 on actual resources, generates the real
product `R` class and compiles all owned production Java plus shared Qt bindings,
Web, Snapshot, Documents and diagnostics against SDK 36, QtAndroid, AndroidX
WebKit/Core and Guava APIs. It uses no bootstrap/test API stubs. Downloads are
bounded and checksum-pinned. Only the 132 KB Qt Java API is retained from the
verified published Qt dependency archive; its independent hash permits a small
cache. SDK tools are copied fresh from the runner's selected SDK, not restored
from an untrusted dependency cache. Candidate compilation has no network.

The reviewed Java API baseline is the published
`qt/5.15.18-2026.01.04@overte/stable#4fc772a2dbcd84731eb6ff9904e6e358`
recipe declared by the current Android products. Its `QtAndroid.jar` SHA-256 is
`a9f64f066766e3908d64183a49c0722aff09495c5f17768213a2989a73edf893`.
The compiler reads the declared reference as syntax/data and rejects a provider
change until its real Java API baseline is reviewed. This is a compatible,
version-bound API baseline, not proof that a legacy native dependency archive
equals Pico's current independently frozen source-graph/runtime payload.

This tier establishes Java/resource compilation. It does **not** establish an
APK, Gradle configuration, Android native cross-compilation or a device run.
Relevant native/host regressions continue to run. Linux C++ test results must
not be described as Android ABI/native-build evidence.

The current manual Phone/Pico builds deliberately use trusted self-hosted
runners and must not receive untrusted PR code. They are not a safe substitute
for a hosted PR build. The current Pico producer also consumes a frozen Shared
source graph; its legacy `deps --download` path can use `--build=missing` and
rebuild Qt. A future automatic Android-native owner requires a separately
qualified immutable SDK/NDK/Gradle/Conan/source-graph runtime and an offline
`--build=never` acquisition/execution contract before it can claim APK/native
acceptance. The Java tier does not silently assert that missing guarantee.
Production Kotlin sources are explicitly refused by the Java compiler owner;
they require a real Kotlin/target compile owner. An existing `.java` inventory
must never make an added `.kt` file appear compiled.

## Existing host suite selection

The complete reviewed platform inventory remains mandatory authority. A narrow
Phone-production-Java-only case omits unrelated dependency-transport, Pico,
bootstrap and independent C++ UI/audio suites. It retains six potentially
relevant Phone/shared contracts and adds the real SDK source compiler. Every
supporting harness tree is bound by an exact reviewed Git fingerprint in
`.github/pr-ci-platform-inputs.json`. An evolving harness, mixed change,
unrecognized path or incomplete scope selects the complete profile instead.
This is not a claim that an unexecuted command has succeeded.

The Phone runtime launcher has two distinct subsets: its ordinary invocation
executes the first three inventory/IME/provenance checks; `--execute` executes
the later Qt/GLM runtime checks. Their similar names do not make them duplicates.

The complete iOS host launcher remains the conservative fallback. No independent
input graph has yet established safe exclusions for all of its individual
contracts. Same-source host receipt handoff still avoids repeating the launcher
inside its own selected iOS build chain.

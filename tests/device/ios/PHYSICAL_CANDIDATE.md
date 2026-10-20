# Physical iOS E2E candidate consumer v1

`ios/tools/candidate/verify_physical_e2e_handoff.py` composes existing readers;
it does not build, install, stage, sign or run a client. The old IO-001 simulator
preflight remains unchanged. Native binding accepts exactly one of its original
`--candidate-manifest` or new `--physical-candidate-metadata`, alongside the
existing independently frozen source/artifact/input/version/channel/evidence
flags. The physical path is now composed with
[installed-code binding](INSTALLED_CODE_BINDING.md). It requires actual native
bundle/PID measurements before a session description can advertise identity.

## Required independent inputs

`--artifact-root` contains the existing signed-device runtime handoff and final
IPA. `verify-runtime-candidate.py` validates that exact original package in iPad
mode, its thin arm64 Mach-O/iPhoneOS platform, bundle/signing/runtime metadata
and original bytes. E2E build markers are mandatory. Simulator packages fail.
No simulator build or receipt is relabeled as a physical package.

`--physical-candidate-metadata` selects the original opaque General terminal
metadata and sidecar consumed by the published SH-002/v002 adapter. That exact
reader must accept all four existing mandatory tiers for **the same physical
IPA SHA**, source, normalized inputs and toolchain. The consumer calls the
original `bind_shared_evidence` API with independently frozen normalized-input/
toolchain values. Merely hashing reader source or copying simulator receipts
cannot satisfy this binding. General's metadata/receipt schema is not copied or
weakened. Supplying source-bound terminal evidence remains the producer's job.

The original pinned SH-009 identity reader validates the actual artifact bytes,
iOS product/channel, minimum version, all original package/generated/SBOM file
hashes and independently supplied frozen inputs. The original pinned SBOM-pair
CLI still validates the bound private snapshots with its official format and
cross-document validators. No dependency installation or network fallback is
available. Runtime selection/artifact bytes are independently rechecked after
these joins, and the actual source checkout must still have the exact clean HEAD.

The original-bundle algorithm additionally hashes the final IPA's actual app
files. This expected app-content manifest remains separate from the later
native measured manifest; it is not returned as a measured device result.

## Offline result and native binding

The result includes `physicalHandoffVersion:1`, status
`IOS_PHYSICAL_CANDIDATE_BYTES_BOUND_VERIFICATION_PENDING`,
`sharedEvidence:"BOUND"`, `sharedBuildInputJoin:"BOUND_TO_INDEPENDENT_INPUTS"`,
original `artifactIdentity`, `sbomPair`, `bundleIdentity`, a bounded runtime
selector (`platform,artifact,bundleIdentifier,appRoot`) and
`physicalDevice:"NOT_EXECUTED",simulator:"NOT_EXECUTED"`. It is an offline byte/
input association, not signing acceptance or device/product qualification.

`candidate_preflight` retains its 90-second subprocess bound, private discarded
stdout/stderr, whole output-size/identity/SBOM checks and read-before-target
ordering. It additionally checks physical protocol version, actual platform,
safe IPA selector, independent tier join and closed bundle metadata. There are
no stage/execute flags. The bound entrypoint continues to refuse installed
identity until a separate native measurement matches this selected content
manifest and an independent actual OS PID/bundle/session source.

Eight host cases execute original physical-runtime, actual SHA/input identity
and original terminal CLI readers using deliberately synthetic IPA/Mach-O and
receipt fixtures. They reject skipped/missing cold tiers, a coherent foreign
cohort, altered evidence/source/version, dirty source, wrong SBOM summaries,
simulator packages and forged preflight output. Immutable-release packaging and
the official SBOM-format boundary are injected in these logic tests. The current
interpreter lacks the official SPDX/CycloneDX/PURL validators; production
verification consequently remains unavailable there. No packages were installed,
and no synthetic receipt is promoted to real build or acceptance evidence.

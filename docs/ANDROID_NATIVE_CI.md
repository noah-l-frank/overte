# Android native CI infrastructure

Local qualification covers the parent-owned common Android native harness and
separate owning Phone and Pico unsigned APKs. Protected policy binds their actual
source, build, verification and dependency receipts to the sealed public payloads.
GitHub Actions remain disabled pending separate runner and activation decisions;
local build/package acceptance does not establish hosted or device acceptance.

The source-only producer's completed bootstrap and host-tool phases are retained
as original evidence. A separate guarded continuation may reuse only packages
whose recipe revision, package ID, package revision, dependency graph and original
successful build are verified. It must additionally verify the original package
manifest revision and an independently sealed SHA256 payload inventory. Conan's
cache-integrity command alone does not establish that identity. A cache hit or
skipped graph node is never relabeled as a newly executed build.

Phone and Pico retain distinct owning application qualification. A dedicated
Pico CI profile may explicitly share compatible prepared dependencies, while
requiring its own input mapping, OpenXR graph, actual native link and unsigned
APK verification. It does not alter the existing Pico release-consumer contracts.
The Android parent branches use the parent-owned common native harness and do
not select a child application's APK merely because its files are present.

## Runner selection

Only an Android owner with a nonempty authenticated `android_native_products`
selection requests `[self-hosted, Linux, X64, overte-native-large-disk]`.
Java/resource compilation and Groovy-only contracts stay on `ubuntu-24.04`, as
do the other central workflow jobs. The job still requires the shared plan and
protected policy; runner selection grants no execution or merge authority.
An unavailable matching runner leaves the native job queued rather than moving
it to a smaller hosted worker.

The custom label must belong to an isolated, ephemeral Ubuntu VM. It must not
expose workstation files, credentials, host container sockets or device-lab
services. Candidate native execution retains its separate offline, nonroot
container boundary and all protected capacity and payload checks. Registering
the runner and enabling Actions are separate operations; this workflow change
does not perform either operation.

## Immutable payload transport

`tools/repository-checks/pr_ci_android_runtime.py` records every payload file's
SHA256, size and permissions, every directory's permissions, and each confined
relative symlink. Modification times are deliberately excluded. The inventory's
own digest must be supplied by reviewed protected policy outside the downloaded
payload. Recomputing a local inventory cannot authorize modified dependencies.

Archive extraction requires both the protected archive digest and exact size,
and verifies the full inventory before making the destination available. The
extractor refuses absolute or noncanonical paths, hard links, device files,
duplicate or unlisted entries, escaping symlinks, and pre-existing destinations.
Restored dependency caches require the same complete verification before use.
An inventory proves transport integrity only; original build provenance, exact
toolchain/profile identity and actual product qualification remain separate.

The producer can write an inventory outside the payload directory:

```sh
python3 -I -S -B tools/repository-checks/pr_ci_android_runtime.py inventory \
  --root "$PAYLOAD" --output "$INVENTORY"
```

Export the sealed payload without executing it:

```sh
python3 -I -S -B tools/repository-checks/pr_ci_android_export.py \
  --root "$PAYLOAD" --inventory "$INVENTORY" \
  --inventory-sha256 "$PROTECTED_INVENTORY_SHA256" --out "$ARCHIVE"
```

The export preserves the inventory's file and directory permissions and confined
symlinks, normalizes timestamps and ownership, and emits regular archive entries
for filesystem hardlinks. Publication never overwrites an existing archive.

Before consuming a locally prepared or restored payload:

```sh
python3 -I -S -B tools/repository-checks/pr_ci_android_runtime.py verify \
  --root "$PAYLOAD" --inventory "$INVENTORY" \
  --inventory-sha256 "$PROTECTED_INVENTORY_SHA256"
```

Run the focused transport regressions without downloads or builds:

```sh
python3 -I -S -B tests/pr-ci-android-runtime-test.py
```

The executing consumer runs candidate CMake/Gradle only inside its
credential-free, network-disabled boundary, with a checksum-bound SDK/NDK,
prepared host tools and target dependency graph. PR execution must never build
missing Conan dependencies or run a cold source producer. npm lockfiles, docs,
unrelated JavaScript and owning Java/resource-only changes retain their narrower
existing checks rather than triggering the Android native consumer.

## Qualification and selected execution

`.github/pr-ci-android-native.json` is protected controller policy. Its initial
`awaiting-local-qualification` state grants no build or merge authority. Activation
requires all three owning baseline executions, sealed public release assets and
exact source/configuration, SDK, runtime and toolchain image identities. Updating
payload bytes cannot reuse an older baseline receipt for those different inputs.

Qualified policy supplies capacity budgets derived from completed payloads and
actual retained build outputs, with explicit reserves for transient work. These
reserves are modeled bounds, not measured disk high-water marks. The cold
`bootstrap` check runs before host setup and cache restore. The `prepare` check
then covers remaining materialization, and `execute` covers the remaining build
budget, without charging completed setup twice. Each check verifies available
RAM, applicable cgroup limits, filesystem space and inodes; workspace and Docker
space requirements are added when they share a filesystem. A transport-only
Groovy fixture does not request native capacity or image/SDK setup. Missing
measurements or budgets cannot authorize a native run.

`pr_ci_android_assets.py` checks public fork release URLs, exact byte counts and
SHA256 digests. A damaged optional transport-cache leaf is discarded without
following its target; only newly verified bytes replace it. Archive extraction
checks every payload byte before publication. The isolated worker repeats the
runtime and SDK checks through the actual read-only mounts before executing any
candidate program. The host avoids repeating those large scans between these
checks; it authenticates the ledgers and the smaller controller/proof documents.

`pr_ci_android_native.py` joins protected policy, owning dependency declarations
and actual execution. Changed dependency declarations require a separately
qualified producer graph and are rejected before expensive setup. The worker
`pr_ci_android_worker.py` runs fixed offline common/Phone/Pico build commands,
stops candidate descendants before trusted output verification, and writes a
source-bound receipt only after the actual build and owning verifier succeed.
The PR consumer never invokes Conan or resolves missing native dependencies.

The Android parent owns a common native build. Phone and Pico own separate
unsigned APK outputs, ELF64/AArch64 checks, 16 KiB alignment and packaged native
dependency closure. These checks establish build/package acceptance, not device
journey acceptance. Infrastructure fixture suites follow their reviewed exact
input closures; changing a fixture alone does not request an application build.

The Pico input-loader fixture executes real Groovy with two checksum-bound JARs
from the existing pinned Gradle distribution. Its small transport cache is
separate from native payloads and is prepared only when that fixture's exact
input closure is selected. Missing Groovy is a CI prerequisite failure rather
than a skipped check. These host fixtures do not download an SDK or start a
native build.

## Offline execution boundary

`tools/repository-checks/pr_ci_android_boundary.py` constructs the isolated
consumer invocation using the exact prepared image ID, the fixed local Docker
daemon and an empty temporary Docker client configuration. Candidate programs
receive no host credentials, Docker socket or host system mounts. The container
runs as a nonroot user with no capabilities, no network, a read-only filesystem,
the default Docker security policy, four CPU cores, an 8 GiB memory limit
without container swap, and a bounded process count. Android and Java preferences
use private writable homes; protected output verification uses a fresh home.

The dependency payload and SDK are mounted read-only. Only the private candidate
and build scratch are writable; candidate Git metadata stays read-only. The
caller supplies a separate small reviewed controller directory. Product identity
is explicit: the Phone/common host mapping is not exposed to Pico, whose owning
adapter requires its distinct graph. On interruption or timeout, the launcher
removes only its own unique container and does not retry the build. Failure to
confirm cleanup is reported separately. Constructing this boundary does not
verify payload provenance or establish product acceptance.

The Phone dependency sentinel's writer creates its lock and takes an exclusive
lock before replacing evidence. Its consumer requires that existing regular lock
file and takes a shared lock through a read-only descriptor. Missing or symlinked
locks fail; verification never creates state inside the immutable payload.

The same immutable payload also appears at `/prepared`, where candidate source
cannot shadow its inventory. Proof documents live separately at `/qualification`
to avoid self-referential inventory hashes. On SELinux hosts, prepare container
labels only on the private exported copies; retain the enforcing security policy
and leave the original SDK and producer attempt unchanged.

The original image configuration and its exported Docker manifest have separate
pinned identities. The launcher accepts those two engine representations only
after comparing the actual configuration digest and every ordered uncompressed
filesystem layer. This supports the containerd image store's manifest identity
without relying on a mutable tag. See the
[Moby containerd inspection implementation](https://github.com/moby/moby/blob/master/daemon/containerd/image_inspect.go).

Run boundary construction and lifecycle tests without a build:

```sh
python3 -I -S -B tests/pr-ci-android-boundary-test.py
```

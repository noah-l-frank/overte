# Original installed-bundle byte source v1

`InstalledBundleIdentity.h`, `bundle_identity.py` and `bundle_observation.py`
provide a measured byte-association component. Both v1 contracts are registered
in this iOS branch's existing contract registry. Native code is uncompiled and
no device/IPA was executed. Host fixtures contain deliberately synthetic file
bytes and validate test/protocol logic only. This component does not advertise
complete feature operations or unlock the canonical installed-code gate.

## Source and request

The E2E-only hook `Test.featureIOSBundleObservation` exists only with both iOS
and `OVERTE_E2E_FEATURE_TESTS`, an explicit test script/results directory and a
valid lifecycle source. Its exact input is `{schemaVersion:1,commandId:
"ios-<32 lowercase hex>",action:"ios-bundle-observe"}`. No requested digest,
archive, bundle name, path, expected manifest or filesystem selector is accepted.

The original CoreFoundation main-bundle URL and executable URL must resolve to
the actual Qt application executable in the original `Overte.app`. An async
worker reads only that original root. It walks original regular files and
directories through original descriptor-relative no-follow opens, retaining
kernel inode/mode/link/size/mtime/ctime records, hashes all actual file bytes,
and verifies those records after traversal. Symlinks, hardlinked files, special
nodes, unsafe/ambiguous names, changes during reading and timeouts fail closed.
No file is modified or extracted. Bundle IDs come from actual CoreFoundation.
Original file paths and kernel identities stay native/private.

Limits are 20,000 nodes, depth 64, path/name UTF-8 lengths 1024/255, 1 GiB per
file, 2 GiB total, 90 seconds initial hashing. Each ready read rechecks the
original root and every retained original node, including directory records
that detect added/removed children, with a 1500 ms native budget. Hashes are
reused only while all original kernel records still match. Any mismatch makes
this source unavailable for its lifetime. Native wall-clock regression fails.
Asynchronous work is read-only and at most one job exists in the Test source.
Its root descriptor closes when its native state/process is destroyed.

The probe preserves the native response in the fixed original private
`ios-installed-bundle-observation.json`. It refreshes the same pending request,
then stops after a ready/unavailable result; it never rehashes continuously.
Missing hooks return explicit unavailability and never a claimed checksum.

## Canonical original byte manifest

The host independently reads the selected original IPA as a stable no-follow
file, verifies its independently supplied archive SHA-256 before/after reading,
and hashes its original `Payload/Overte.app` contents without extraction.
Malformed, duplicate, unsafe, symlinked or competing app entries fail. Implicit
ZIP parent directories are included, as are empty files/directories. The actual
Info.plist must identify a regular app executable and an enabled E2E test build.
These metadata checks do not pretend to be execution or build provenance.

The canonical root is SHA-256 over ASCII `overte-ios-installed-bundle-v1` plus
one NUL, then records sorted by NFC-normalized relative UTF-8 name bytes.
Each record is exactly: `D|F` (one ASCII byte), four-byte unsigned big-endian
path length, path bytes, eight-byte unsigned big-endian size, 32 raw SHA-256
bytes. Directories use size zero and SHA-256 of empty bytes. Reject names that
collide after normalization/case-folding; files require their actual parent
directory records. Original ZIP compression/order/timestamps do not participate.

The exact bundle result is `{bundleContractVersion:1,bundleId,bundleSha256,
executableSha256,nodeCount,fileCount,totalBytes}`. All actual app files participate,
including executable, QML, Scripts, Info.plist and signature/provisioning files.
No expected value is copied into this measured source. Matching the content
root is an association with the selected archive's app bytes, not a claim that
the native process read an IPA or measured its ZIP checksum. Re-signing,
thinning or other installation transformations require a separately qualified
final artifact; this component never normalizes a mismatch into success.

## Fresh private observation and correlation

The exact envelope is `{bundleObservationVersion:1,commandId,instance,sequence,
processId,capturedEpochMs,status,preparedEpochMs,bundle}`. Status is
`pending|ready|unavailable`. Pending/unavailable have preparation time zero and
an empty bundle. Ready includes original completion time, independently of the
fresh file-inventory validation/capture time. Source instance, PID and sequence
are native birth/process/read values, never host request counters.

`NativeBundleObservation` sends once and polls the original file for at most
100 seconds/1001 reads. Native PID/instance stay pinned, sequence/time cannot
regress, and an identical pending sequence may only repeat an identical frame.
On ready it separately acquires a fresh original `feature-native-observe`
clock/PID sample and enforces the existing -250..1500 ms freshness window.
Host UTC never substitutes for native time after a long initial hash. Repeated
ready acquisitions must preserve the original bundle and preparation time.
Ignored input, absent/foreign files, source changes and stale correlations fail.

`FeatureObservation.installed_bundle()` connects this component to the original
private HTTP/AFC transport and that separate native-clock acquisition. Private
command/response files remain owned by the existing session. Full lifecycle
cleanup must drain any hash worker and remove only its original owned response
after verified process/source retirement; a successful file-input ACK alone is
not cleanup. No caller may substitute archive expectations or a primary sample
for the independent native bytes.

## Remaining canonical binding work

The legacy canonical preflight calls the IO-001 verifier, whose
audited artifact is a simulator ZIP, not a physical IPA. It cannot be treated
as a physical candidate receipt. The new
[physical candidate consumer](PHYSICAL_CANDIDATE.md) retains independently
validated source/input/SBOM/artifact provenance and selects the final physical
IPA. Comparing the native measured bundle above and actual OS process before
reporting executionIdentity remains the next separate join. The simulator
preflight stays unchanged.

The component's `mobile:overteProcessInfo` path also depends on a prepared driver
extension. Replacing it indiscriminately with `activeAppInfo` would identify the
foreground system app during backgrounding. A standard foreground OS PID source
may be used for bounded bootstrap, with explicit separately measured background
state and new native birth/PID guards after return; never invent a cached PID as
a fresh background observation. Those integration changes remain open.

Until this complete chain exists, `OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE`
and missing complete capabilities stay authoritative. The nineteen host cases
cover independently read original app/IPA bytes, changed QML/Script/executable/
signature/plist, unsafe/foreign files, framing, original private transport,
pending/replayed/foreign/changed sources, native-clock correlation and original
probe grammar. They do not execute or validate the C++ worker or an installation.

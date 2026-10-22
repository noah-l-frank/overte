# Snapshot native file responsibility

The optional `OVERTE_E2E_FEATURE_TESTS` + iOS + `OVERTE_IOS_E2E_TEST_BUILD`
source is active only with `--testScript`. It does not enable the complete
Snapshot feature capability. Native compilation and physical devices remain
unverified. Host filesystem/weak-functor models and actual JavaScript probe tests
qualify protocol logic only.

`feature-ios-snapshot-owned-files` version 1 keeps the original native read
bracket, process/source birth, full run, original empty-prefix query, later list
row and actual `Snapshot::captureStatus`, native `QFile` or `GifBegin` path
association. The first path-observation time and `save-attempt` phase are retained
without claiming a successful write, allowing a terminal failed capture's actual
partial file to remain owned. Capture version 1 and
Snapshot file list/read versions 1/2 retain their existing fields. Pre-existing
nonempty prefixes are never admitted. Processing outputs are admitted only after
the actual terminal capture and its native weak resources have ended; an early
manifest remains the caller’s responsibility while its bytes can still change. Changed rows, source-root changes,
ambiguous capture associations and source bounds fail closed. No caller supplies
a filesystem path, filename, expected hash or claimed absence to the removal
operation.

`feature-ios-snapshot-file-remove` accepts only schema version, fresh command
nonce, run, native file ID and the original native manifest command nonce. A
known terminal capture and its actual weak capture/resource expiry are required,
as is retirement of every actual native file-read functor. Queueing and work use
the same existing Snapshot semaphore. The actual thread-pool functor owns a weakly
observed responsibility token; return/finally and later weak expiry are separate
facts. A cached functor prevents retirement even after the unlink succeeds.

Immediately before the sole `unlinkat`, native code checks the current configured
root, directory inode, exact original file revision, regular single-link file,
whole bytes/hash and original metadata again. It opens through directory/file
FDs with `O_NOFOLLOW` and never recursively removes a directory or prefix. The
result retains whether unlink was actually issued, its success/error and original
native sample time. Failed and uncertain work remains in the immutable source.
The probe consumes the nonce before the native call, even for missing hooks,
exceptions or a busy worker; it never retries that nonce. The separate receipt
is a queue ACK and cannot establish removal.

The Python reader validates original rows and histories by immutable IDs, rather
than list position: new random IDs can sort before older ones. Its `removed`
join requires the expected candidate PID and the exact original remove query,
successful native unlink, normal body return, finally and actual weak expiry.
It explicitly still requires a fresh independently clocked empty manifest and
paired quiet observations. A successful ACK, an empty modeled ledger or a
successful unlink alone cannot retire the feature's ownership.

Remaining integration includes a durable one-send removal owner with original
native reply carriers, candidate/source admission, actual independent post-unlink
absence and quiet observations, error/partial-output recovery, and the complete
capture/export/destination/observer/lifecycle flow. This component does not
supply these results.

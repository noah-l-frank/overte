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

`SnapshotOwnedPacket` now retains each native source query before send and its
exact raw AFC reply in private original frames, preserving whitespace. Original
native getter brackets, independent NativeDiag before/after packets and actual
host acquisition times remain separate. A late reply can be retained as historical
evidence; it cannot pass the unchanged 1.5-second native/host qualification. An
opened complete original after a lost flush is adopted without another query,
AFC read or file rewrite. Partial/unrecorded output remains owned.

`SnapshotRemoveOwner` pins the admission packet's actual owner-journal hash,
file ID and original manifest nonce before its sole send. Candidate verification
and a final age/transport guard run after the issued journal write. An unknown
return leaves the command issued; no input is resent. Its original passive queue
receipt must be retained before another probe command can replace the pending
input. A false queue receipt makes no failure/success claim about native work.
Only later native job originals can establish the result.

Each subsequent source original is linked durably before interpreting continuity
or success. Wrong source births, failed unlinks and still-retained functors remain
owned observations. A later retired job can resolve an old unlink even when that
result original is too late for fresh input admission. Historical reconstruction
reads only original local files; altered admission/result files or journal hashes
fail closed. No source/file owner is deleted by this component.

`snapshot_file_absence` composes the actual retained empty manifests with original
`SnapshotFileWorkPacket` and `SnapshotOwnedPacket` observations, complete remove
owners and independently bracketed native clocks. Each fresh group must fit the
unchanged 1.5-second acquisition window, including final candidate validation.
Every known native file must have its original successful, weakly retired unlink;
every admitted prefix must have been originally empty. Cached read callbacks,
unknown native reads, reused queries, source replacement and reappearing files
prevent a positive result. Historical reconstruction reads actual original files
without SDK access and revalidates each source journal.

The file-only quiet join requires at least three nonoverlapping groups and three
seconds between the first completed and last started original acquisitions, in
host UTC/monotonic and both native file channels. Only those groups' own manifest
reads may be added. This cannot exclude a new capture that writes between file
observations: script/capture/render/export quiet and independent paired feature
cleanup remain explicit requirements. Host checks use actual private file IO,
retained weak functors and historical source files with modeled native/SDK clocks;
they do not establish physical iOS timing or native compilation.

Remaining integration includes paired script/capture/destination quiet, final
file/archive retirement, and the complete capture/export, destination/observer/
lifecycle flow. This component does not supply complete-feature results.

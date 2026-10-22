# Original iOS location bookmarks, version 1

This passive source is a component of the pending Worlds/navigation adapter.
It adds no feature capability or bookmark mutation. Scripts, Authentication and
Graphics remain the three complete source-level areas. Native compilation is
unverified and devices are untested.

`feature-ios-location-bookmarks` accepts exactly schemaVersion 1, an iOS command
nonce, the action and a run ID. The existing private fixture/probe path invokes
`Test.featureIOSLocationBookmarks` once for that request, then saves the original
packet through the existing atomic private `Test.saveObject` allowlist. Missing
hooks produce unavailable evidence. No caller-selected filename, expected map,
requested address or setter is accepted.

The native source exists only under `OVERTE_E2E_FEATURE_TESTS`, `Q_OS_IOS` and
`--testScript`. On the GUI thread it reads the already existing
`LocationBookmarks` dependency through `getBookmarks()` and `getBookmarkError()`.
It never creates a missing service. This follows the existing public native-call
permission semantics; system-script permissions are unchanged. A load error is
retained independently from the loaded map.

The source separately opens the actual fixed
`QStandardPaths::AppLocalDataLocation/bookmarks.json`. It retains original bytes,
size, SHA-256 and the original decimal device/inode identity. Open is read-only,
nonblocking and rejects symlinks; the file must be regular, owned by the app user,
have one link and contain at most 65,536 bytes. Descriptor and pathname identity,
size, permissions, ownership and nanosecond modification/change times must agree
before and after the bounded read. Unsafe, oversized, changing or unreadable
files remain unavailable. Only an actual ENOENT produces absent. These metadata
checks establish a stable read; no filesystem timestamp becomes native freshness.

Original UTC and monotonic clocks bracket both loaded-state and file acquisition.
The packet preserves PID, observer birth UUID, advancing observation counter,
run and request nonce. The iOS HTTP/AFC factory reads a separate nonce-bound
native clock before the query and after its reply. Python accepts an acquisition
within 1.5 seconds, with a matching foreground process, no counter regression or
source replacement, and consistent native clocks. Host monotonic time bounds
transport duration only. Its separate v1 acquisition receipt references the
unchanged original packet hash. Historical validation needs no source factory,
clock refresh or host/AFC modification time.

The loaded map and saved bytes are deliberately independent. The parser reports
absent, unavailable, invalid JSON and a valid empty object as distinct states.
Duplicate keys, non-finite numbers and non-object JSON are invalid. A loaded new
bookmark cannot substitute for a failed disk write. Non-string user data and
load errors are retained for the owning journey to reject, rather than silently
repaired or normalized. Neither the reader nor fixture removes files.

Ordinary product deletion of the final bookmark persists an empty JSON object;
it does not delete the bookmark container. The future journey must verify owned
entry removal and preserve unrelated entries, reporting the actual container
state honestly. This source does not itself prove restoration, restart,
directory consumption, arrival or callback retirement.

Thirteen device-free tests exercise real temporary host file bytes, the actual
Python HTTP/AFC codecs and probe branch, with native services/SDK boundaries
modeled. Counterexamples include ignored persistence, missing/unsafe files,
corrupt JSON, mismatched hashes, stale/reused/foreign originals, changed process
or source birth, lost replies without resend and foreign host UTC. They qualify
source and transport logic only. The native file reader remains uncompiled.

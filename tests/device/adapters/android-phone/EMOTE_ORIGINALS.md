# Private original Emote frame storage, version 1

`overte_phone_emote_originals.PhoneEmoteOriginals` stores immutable canonical JSON
under an explicitly supplied existing private artifact root. It generates no
native facts, effects, timestamps, peer receipts or resource-absence verdict.
Source acquisition v2 and input ownership v2 use it to preserve complete original
records without increasing the existing 64 KiB active metadata limit. The full
Emote capability remains unavailable; native compilation and all devices remain
unqualified.

The two closed namespaces are `sources` and `inputs`. Original files bind the
existing exact candidate/process/session context, run, role, namespace and
one-based index. The exact wrapper is `emoteFrameVersion:1`, `kind`, `binding`,
`runId`, `role`, `index`, `frame`. Each file is at most 1 MiB. It contains actual
retained source packets or an actual complete input row; native/feature semantic
validation belongs to their existing owners and is repeated during replay.

An original ownership record has exactly `emoteOriginalVersion:1`, `kind`,
`binding`, `runId`, `role`, `index`, `sha256`, `bytes`, `phase`, `file`. Phase is
`planned`, `opened` or `saved`. Planned has `file:null`; opened/saved have exact
actual filesystem `device` and `inode`. `sha256` covers the complete canonical
UTF8 wrapper bytes, and `bytes` is their original length. The immutable name is
derived solely from namespace/run/role/index/digest, never from a caller path.

The writer persists planned intent before exclusive no-follow creation, then
actual opened identity before bytes, then saved ownership only after complete
write, flush/fsync, independent reread and exact digest/context validation.
Existing files are never overwritten, even for an identical payload. Failure
after open leaves that exact partial file and its ownership responsibility.
Missing results, guard loss, size/type errors and a five-second monotonic I/O
deadline cannot return successful storage.

Reads require private-directory ownership, a regular 0600 file with one link,
the original device/inode before and after read, exact byte length/digest,
canonical JSON and the complete original wrapper scope. Equal bytes copied into
a replacement inode are rejected. Symlinks, hardlinks, public permissions,
foreign roles/candidates/namespaces, missing/truncated data and changed bytes
are unavailable. Original clocks inside a frame are never changed.

An index has exactly `emoteManifestVersion:1`, `kind`, `binding`, `runId`, `role`,
`block`, `entries`. Each of at most eight blocks contains at most 128 entries.
Compact entries have exactly `index`, `sha256`, `bytes`, `device`, `inode`.
Index references have exactly `block`, `count`, `sha256`, `bytes`; their digest/
length cover canonical index JSON. Index files use the unchanged private
metadata writer and 64 KiB cap. Their names are content-addressed; every update
creates a new immutable index and preserves earlier ones for diagnostics.
Planned and saved index intents are persisted around each index write. Source
and input owners record those write responsibilities independently.

Restoration checks complete contiguous indexes, original scope, every file
identity/digest and exact total count before returning historical records. It
does not contact a device or turn history into a fresh result. Source/input
owners then rerun actual native, widget, code, phase and receipt validators.
All 1,024 records fit eight small active references; no prefix is silently
dropped. The current input row and all completed input rows preserve the
existing closed behavior contract.

These are private evidence artifacts, separate from active product resources.
Complete cleanup must verify actual native/input/timer/callback absence and
quiet windows first, archive the exact source/input owners and index roots,
and retire only those hash-scoped active metadata records. Immutable evidence
must remain available for historical verification. This storage component has
no API for deleting foreign files or claiming successful product cleanup.

The affected 139-case host selection passes. It covers all 1,024 stored records,
the 169-input maximum shared Sit-discovery storage path, reconstruction beyond
512 Script originals, original file replacement/corruption, interrupted writes,
lost guards, namespace/role/candidate separation, and preservation/rejection of
legacy inline journals. Existing Phone inventory, documentation and version
registry checks also pass. These are host logic checks with synthetic native
boundaries; no build or physical client was used.

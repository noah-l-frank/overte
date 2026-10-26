# Snapshot Share frozen source originals

The admission seal closes the Archive's original bundle reader. Four further
global outputs also need first-file ownership before they can be retired:
the final chunk, exclusive retirement intent, retirement result and latest
retirement observation. The Share Archive now publishes these through one
process-owned `OVTShareSourceOutputs` catalog. This remains a Feature 11/14
component; the complete capability stays closed and the source-complete count
remains 5/14.

## Native publication and lifetime

The catalog retains its initial Documents parent and current published file
facts. Its API admits exactly four enum values with fixed native filenames.
Every publication requires actual first-name absence or the unchanged previous
owned version. The retirement intent keeps exclusive creation. The other
outputs use exclusive temporary writers, synchronization, actual writer-to-
published-inode comparison and parent-relative original byte reads. A new
current version is recorded only after every original reader/writer and parent
descriptor closes successfully. The catalog copies the actual published bytes;
it does not reconstruct a prior intent or result from later JSON state.

The existing run-retirement producer uses the same catalog for its intent and
each actual result update. Initial root/file guards, named unlink/rmdir steps,
native event clocks and literal version-1 run-retirement records are preserved.
A failed or unknown publication keeps its files and temporary names owned.

Once the admission seal returns an original close record, the catalog fences
all four producers. The Archive also guards ordinary import, chunk, retire and
retirement-inspect controls before further effects. This lifetime belongs to
the original process singleton, so a recreated controller cannot reopen those
producers or re-anchor the existing source files. The admission source's
identity/clock producers keep their own original fence.

## One readonly inventory

A separate normal nonce-only control reads the six fixed source files against
their first published facts. It checks the original Documents parent and the
exact reserved source-name census before and after no-follow original reads.
Unexpected `snapshot-share-*`, `.record-*` or `.companion-*` names remain owned
and block qualification. The source records actual original-file revisions,
hashes, lengths, descriptor closure, native clocks, catalog identity and the
exact admission-seal byte hash.

The inventory contains the actual copied retirement-intent/result bytes in two
closed fields. The other four byte originals already exist in the admission
and Share host journals. The native inventory is serialized once and exposed
through a readonly label backed by the original catalog. It creates no further
output file. Its normal input accepts a fresh nonce and no expected paths,
hashes, byte counts or desired result.

`SnapshotShareSourceInventoryOwner` requires completed original Share run
cleanup and the independently retained admission-seal proof. It reuses the
existing once-only UI/WAL owner through a closed subclass; admission-seal
literal defaults and readers remain unchanged. The inventory's action,
envelope and original files use their own exact namespace and schema keys.

The host joins all six file hashes and lengths to actual original bytes. The
retirement-result body must equal the original completed native retirement
record; the actual exclusive intent must contain that same operation's initial
state. Source instance, PID, seal bytes, parent, original output ordering and
UTC/monotonic ordering are independently bound. Lost button or readonly-value
returns retain the same original without another native inventory. Unknown
current files and same-byte inode replacement remain unqualified. Pure history
reopens all originals without a live SDK or writes.

All six native files remain present. Their conditional unlink, exclusive final
intent, original post-deletion absence windows and actual process/SDK retirement
are still required. The capture/page, upload, independent Actor and complete
outer journey also remain open. Native source remains uncompiled and the
repository process plugin uninstalled. No compiler, build, device,
installation, laboratory, service or remote operation was used.

## Host validation

The first explicit connected inventory case passed in 22.518 seconds
(`share-inventory-resume-20261026-01.log`). It preserves the real Share/run
quiet periods, closes the modeled source's actual host descriptor, joins all
six real original files, rejects bound-field/raw-body/profile substitution and
replays the proofs with live sources and writes forbidden. UIKit, NSBundle,
native source execution and OS/native clocks remain declared model boundaries.

`share-inventory-resume-20261026-02.log`: all five connected inventory cases
passed in 89.006 seconds. They include all four producer fences before further
effects, lost button/read-value recovery without another native query, an
identical-byte global file replacement and an unexpected reserved source name.
The latter files remain physically present and unqualified.

`share-inventory-resume-20261026-03.log`: 35 exact compatibility cases passed
in 32.121 seconds: twelve admission-seal cases, six original Share actions,
two original Share packet profiles, seven Share admission, five Photos source
and three installed Share factory cases. The admission-seal default envelope,
slots, original files, acquisition clocks and recovery behavior remain intact.

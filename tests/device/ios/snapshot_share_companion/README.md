# Separate original Snapshot Share receiver

This is a standalone, explicitly selected test application and Share extension,
not an Overte product target. No native configuration, compilation, signing,
installation or device execution has been performed. The source entry requires
the Xcode generator, iOS, `OVERTE_E2E_FEATURE_TESTS`, a separate bundle identifier
and an explicitly provisioned App Group. It neither chooses signing credentials
nor changes the client, a global build or laboratory configuration.

The extension accepts exactly one actual `NSExtensionItem` attachment. Normal
UIKit fields contain only the run, observed capture basename and inspection
nonce. There is no expected digest, byte count, image or success field. It
selects one actually advertised concrete image type matching the observed file
extension; ambiguous types, extra attachments and foreign filenames fail.

**Receive original file** exclusively creates an owned App Group run directory
and synchronizes its intent before invoking the provider. A second tap or an
existing run directory refuses another request, including after an unknown
return or process replacement. Partial records and files remain diagnostic
responsibilities. No reconstruction starts a new provider read.

`loadFileRepresentationForTypeIdentifier:completionHandler:` supplies the actual
temporary file. Its bytes are copied unchanged inside that callback, before
returning. Apple documents that the [temporary representation is deleted after
the completion handler returns](https://developer.apple.com/documentation/foundation/nsitemprovider/loadfilerepresentation%28fortypeidentifier%3Acompletionhandler%3A%29).
There is no preview, UIImage, encoder or generated image source. Copying checks
the opened regular-file identity, size and modification/change timestamps,
hashes the actual written bytes, bounds them to 256 MiB, and synchronizes the
exclusive private output. Metadata is bounded to 256 KiB and atomically replaced
with file/directory synchronization. Histories retain every event and inspection
up to their closed bounds; overflow fails instead of trimming old evidence.

The actual callback retains `OVTShareRead`; the journal holds it weakly. Body
completion and actual object deallocation are separate recorded events.
**Inspect original owner** adds a fresh unique nonce and the extension's own
native UTC/monotonic clock with its actual weak state. **Finish receiving** is
allowed only after completion and a separately inspected expired read owner.
It records one finish intent before the real extension completion call.
Finishing does not prove that the extension process, presentation or completion
machinery disappeared. The enclosing feature must measure those separately.

After normal Share completion, the containing application's **Import unchanged
Share original** button exclusively creates a Documents run directory. It first
persists an import intent, copies the original bytes without conversion and
checks them against the original extension digest. It rereads the original
extension metadata and requires identical bytes, then exposes that unchanged
metadata and a separate native import envelope. This transfer never retimes the
extension's clocks or presents an archive read as a live extension observation.
A repeated import or existing output directory is refused.

`snapshot_share_original.py` validates the separate version-1 and version-2 native and import
contracts, immutable histories, genuine callback entry/return/weak expiry,
unique fresh live inspections and concrete image types. The final byte join
requires equality with the independently acquired original Snapshot file,
the actual successful client Share callback, matching controlled filename and
run, and original UTC ordering across processes. Their monotonic epochs remain
separate. A successful activity ACK, cancelled Share, transformed file, stale
inspection or held callback cannot supply that join.

The [anchored archive chunk source](../SNAPSHOT_SHARE_CHUNKS.md) adds actual
initial file/run identities to version 2 and an ordinary read-only 512 KiB
chunk input. Its literal version-1 readers remain exact and independent. The
admission-bound AFC facade reads unchanged source metadata and bounded archive
chunks; it provides no extension process-absence or cleanup acknowledgement.

Eight host tests exercise actual private files, original byte digests and the
client native-export codecs over modeled UIKit/provider/process observations.
They also parse the standalone plists without configuring CMake. These tests
do not execute Objective-C or qualify packaging, signing or a device.

Whole Snapshot integration still requires admitted installed code for both
applications and the extension, normal candidate-bound system-sheet inputs,
original AFC acquisition, export/capture responsibility and byte provenance,
independent witness, permission recovery, deletion of owned destination/private
artifacts, repeated quiet retirement and measured extension process absence.
The byte receipt retains `extensionCompletionRequired` and `cleanupRequired`;
it advertises no complete feature capability. Neither this receiver nor the
separate Photos resource reader substitutes for the other destination.

The [independent Share archive admission](../SNAPSHOT_SHARE_ADMISSION.md) now
binds its selected final app and embedded `.appex` byte forests to original
installed native observations. It uses a separate compile-time identity/clock
profile and existing bound SDK; source and host models are tested without
compiling this target. Live extension/system inputs, actual original transfer,
process absence and retirement remain separate obligations.

The [frozen source inventory](../SNAPSHOT_SHARE_SOURCE_INVENTORY.md) adds first
publication identities for all six global outputs, fences their producers
after admission-reader closure, and retains their original byte joins through
one readonly normal input. All six files still require conditional retirement;
this inventory does not enable whole Snapshot acceptance.

The [conditional source retirement](../SNAPSHOT_SHARE_SOURCE_RETIREMENT.md)
then removes exactly those six pinned files and its own exclusive final intent.
Actual unlink/sync/absence results and fresh native-file/Node/host quiet windows
remain separate original proofs. Process/SDK retirement and the complete outer
Snapshot journey are still required.

The standalone packaging uses CMake's [App Extension embed phase](https://cmake.org/cmake/help/latest/prop_tgt/XCODE_EMBED_type.html)
and Xcode's explicit [Info.plist build setting](https://developer.apple.com/documentation/xcode/build-settings-reference).

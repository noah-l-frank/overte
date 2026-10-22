# Original Pico Chat application v1 and archive closure v4

The private `PicoChatComposition.restart_and_close_application(after_epoch)` and
`finalize_application()` extend its existing deferred-cache branch. They do not
register public Chat operations or a complete capability. All device/network
qualification and a hermetic peer build receipt remain absent. ActorSource2's
actual compiled configured source metadata is retained with that explicit limit;
the Pico APK revision is never substituted for the peer's source revision.

`PicoChatApplicationClose` uses the existing `RestartInputs` and
[PicoChatRestartIO](CHAT_RESTART_IO.md). It preserves the exact held original
host session cursor. Stop and launch each have a durable child and parent intent,
an unchanged independent cleanup-ticket fence immediately before the actual
single SDK command, and no facade bootstrap, repair stop, retry or cursor discard.
Lost receipts leave issued ownership. The original PID selection is OS evidence,
not ESRCH. Only the actual new process's native kernel source can prove ESRCH.

Before replacing any host cursor, new unbound read-only sources establish a
strictly different numeric PID with greater original start identity, native
instance and actual lifecycle counters, original old-PID ESRCH, and new profile,
settings-worker and View births. The passive current profile must match the
retained saved original cache, queued writer and independently acquired physical
INI/registered JSON fingerprints exactly. It neither acquires a new profile nor
calls a second Restore. Every original copy, guard, CAS and final native clock
shares the unchanged 1.5-second budget. The actual original host cursor transfer
runs under its existing canonical lock with only host CAS/elapsed checks inside;
HTTP, SDK, candidate and native queries stay outside that lock.

`_chat_postrestart_sources` constructs two independent fresh compiled code and
cache-absence roles, with the parent's exact two source-lock objects and new
private namespaces. It does not read, rewrite or reconstruct the old normal
Script manager/UI journals. Original runtime binding reads the actual new tablet
bridge without input. Its primary Chat writer accepts Inspect only; no new cache
is created. The peer uses new Inspect-only `OwnedChatPeer.retirement_reader()` instances
on the original still-owned restricted retirement transport. A lifetime-wrapped
reader is rejected; its action callback is never unwrapped or adopted. Primary absence has no Open/Retire IDs in its new native
birth; the peer retains its exact original retired source and mutation IDs. The
new actual domain connection birth differs while the independent peer's domain
UUID hash remains the same. Code roots/assignment/V8 sources remain original.

The two roles must observe three complete seconds on host and all seven native
source clocks, with each consecutive gap in `(0, 500]` milliseconds. The original
physical profile remains unchanged. Only then is the retained peer observation
IPC closed once. Original command/result paths disappear, the original host OFD
is closed, and the independent actual actor process FD inventory proves the old
result descriptor absent. A second complete three-second quiet interval samples
actual primary cache, View/VR keyboard, compiled code and native/profile sources.
The peer packet is historical after IPC closure and is never relabelled fresh or
recreated. A late keyboard, page, draft, storage mutation, code change or native
lifecycle change prevents completion. Old QML/context ownership is discharged by
actual old-PID ESRCH, preserving its original old flags and source records.

Before stopping the old PID, `PicoChatArchivePlan` admits only the complete warm
parent's explicit original file descriptions: all consumed Dispatcher steps,
six child kinds, original profile/Erase/input/cache owners, their separate role
and code histories, old manager/UI contexts, and all 26 independently published
Witness stages. Historical reconstruction performs no new publication or input.
Unknown/reading/publishing/unconsumed rows prevent admission. New post-restart
histories and the exact original closed actor-file receipt are added only after
actual completion. Directory enumeration rejects extras; it never discovers or
adopts ownership. Rootless chunks and retained successor/retirement journals also
block ordinary generic cleanup.

`ChatEvidenceArchive` v2 holds original Linux directory descriptions, full file
stamps and exact bytes in explicitly closed immutable snapshots. Legacy v1 keeps
its original held file-description lifetime unchanged. Each source is copied once into a newly created private evidence
directory, with read-only files and a closed hashed multipart manifest. Writes/unlinks use
the original directory descriptors; each original parent is requalified. The
retirement ledger uses compact indices, and the final receipt pins the exact
label count/digest, preserving the existing 64-KiB per-file bound. Only
these explicitly admitted fully consumed originals can be unlinked, each after
durable intent and actual source/phase qualification. The existing
`RestartInputs.retire` runs after its original three owners are absent; it does
not derive ownership from the archive. New actual code, empty cache/View/VR
keyboard, physical current profile, native birth/ESRCH and independent unchanged
cleanup activation are acquired again after final journal removal. Their exact
original final packet is retained in `final.json`; later guards check that same
packet's age, including final writes, marker unlink and directory sealing. A
failure after the marker unlink creates only an explicit CAS-from-absence
failure marker; a landed/foreign marker is never overwritten. No input repeats.

Sealed evidence directories have mode 0500 and files 0400. Live ownership stays
private mode 0600 under original 0700 parents. The finite archive bound is 4096
original files / 64 MiB, without changing existing source/contract bounds.
Archive content contains the existing fixed test transcript, source identities,
fingerprints and original effect/release evidence. No private setting variants,
actor owner token, fixture credential, device selector or account data is added.
Keep this archive in the private evidence area, outside public reports. Cold
archive checking verifies only exact sealed bytes and scope; it cannot establish
current target state, recover inputs or adopt a partially completed archive.

Host checks use actual private files, strong Linux OFDs, original session/CAS,
RestartInputs, phase validation and source readers. Android SDK/kernel/native,
V8 and preceding 26 input effects are declared producer seams in the component
fixture. Its positive composes restart through both quiet intervals, actual host
IPC/OFD closure and final archival/RestartInputs retirement. Separate actual Pico
factory checks prove new read-only namespaces without old-manager reconstruction,
exact lock objects, no cache input, retained-source refusal and rootless/partial
archive cleanup refusal. No product app, Assignment Client, device, ADB or OpenXR
run is executed, and no full-feature or target acceptance follows from these
host checks. The complete warm Pico catalog is source-present; its full parent
journey remains unqualified until exercised with the required original actors.

Owning selections remain disjoint and lossless under the existing 120-second
catalog budget; the primary integration registers them without widening bounds:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device python3 -m unittest self_tests.test_pico_chat_application_close.application_close_journey_tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device python3 -m unittest self_tests.test_pico_chat_application_close.application_close_recovery_tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device python3 -m unittest self_tests.test_pico_chat_application_close.application_close_admission_tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device python3 -m unittest self_tests.test_pico_chat_application_close.application_close_delivery_tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device python3 -m unittest self_tests.test_pico_chat_application_close.application_close_post_ipc_tests self_tests.test_chat_evidence_archive -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device:android/vr/pico/tests/device python3 -m unittest test_chat_application_close -v
```


The complete shared 25-action Dispatcher/26-stage Witness positive also runs in
`self_tests.test_chat_compiled_dispatcher.CompiledDispatcherTests.test_all_original_25_steps_and_26_independent_compiled_witness_stages`.
It reuses every existing positive assertion and child owner, while selecting
closed Compiled model/absence roles for primary, actor and independent witness.
Each role owns its original root/Script/V8/root source transactions; initial and
active histories share only that role's exact code owner and source lock. The
three-stage prefix separately proves distinct witness source ownership. Native,
widget, network and peer production remain declared seams. This supplies the
complete compiled source/effect history required by the warm catalog; it does
not qualify a complete Pico parent, peer executable or device. Integration uses
this positive in the existing journey selector instead of duplicating its older
uncompiled-model positive, keeping the unchanged 120-second budget and existing
legacy/recovery counterexamples.

The warm whole-parent join additionally exposed two different `history` APIs.
`ChatBackground.history` decodes embedded original packets; `ChatDispatcher.history`
is an audit method. Neither is a `ChatSourceChunks` owner. The archive plan now
admits only actual typed immutable history/chunks, retains the Dispatcher's
separate original chunks, and never invokes either method to invent an archive
source. Unknown non-callable history/chunk owners remain errors. An exact private
namespace inventory runs before the original process stops, in addition to the
final inventory, so unknown roots/rootless chunks prevent process retirement and
remain untouched. The new narrow regression uses actual private files, original
OFD catalogs and immutable chunks, with no target input.
The pre-stop inventory includes the exact already-owned, fully consumed retired
peer reader journal as a known mutable source. It must still serve independent
post-restart queries. Its original closed bytes are admitted into the archive
only at `finish()`; a pending transaction or different original owner is refused.


Archive v2 fixes the measured complete-catalog `EMFILE` failure without changing
`RLIMIT_NOFILE` or the existing 4096-file, 64-MiB and 64-KiB bounds.
`ClosedOriginalFile` reads each explicitly known source through an actual
`O_NOFOLLOW` file description plus kernel alias. It verifies private mode, UID,
link count, size, device/inode, nanosecond mtime/ctime, original bytes, FD-to-path
identity and the continuously held original parent directory. Both handles close
only after actual `F_DUPFD_QUERY` ownership succeeds. Later access is a new
bounded read window of the same already-admitted immutable file; it never claims
that the earlier file description remained open. Every reopened window repeats
the full physical/byte checks. Changed bytes/stamps/parents and lost/recycled
halves fail closed. An uncertain pair remains retained for host finalization;
it cannot close a foreign replacement even when it names the same original file.

Read-only archive copies use the same bounded windows under their held original
archive directory. The v2 manifest explicitly declares
`fileOwnership: closed-immutable-originals`; final and retirement versions match.
The cold reader preserves legacy v1 compatibility and validates v2's closed
field/version boundary. Pico archive plan v2 requires this v2 ownership mode;
a relabelled legacy receipt is refused. A sealed cold archive still proves only
its original bytes and scope, never current device/process release.

The latest 24 affected original-file/archive/plan/Pico-factory cases passed in
19.648 seconds. The 2100-file original catalog stayed within four additional
steady descriptors and preserved the process's exact original RLIMIT tuple.
Counterexamples include same-file FD recycling, identical-byte file replacement,
parent replacement during a read, archive-copy replacement, unknown roots, lost
unlink receipts, final-source expiration and v1/v2 scope relabelling. These are
host filesystem/kernel checks with explicitly synthetic native release sources.
The complete warm parent has not yet passed final archival and remains partial.

The next complete warm host measurement reached all 26 compiled/Witness stages,
normal Erase/profile restoration, both cache retirements, once-only restart,
new-birth/old-PID absence and independent IPC closure with both quiet windows.
It stopped before the first archive unlink: 2623 admitted original files and
native Root sequence 186 would require 5438 requests under the old per-file
Root/Script/Root guard, exceeding the actual unchanged whole-process limit 4096.
That 275.228-second manual diagnostic is not a registered catalog test and does
not change the existing 120-second selection budget or establish whole closure.

Archive/plan v3 therefore explicitly opts into `ChatArchiveUnlinkFence`. Up to
16 unlinks and 250 milliseconds since a complete source acquisition may use
that exact immutable original packet. Its original 1.5-second host/native age
still includes the whole acquisition; the shorter reuse window cannot restart
it. A new full acquisition is permitted only before the next durable unlink
intent. Each actual unlink requires a NEW independent original HTTP phase read
after its last CAS and file check, with the same complete cleanup activation.
Fresh HTTP never refreshes the native packet. Changed accepted reader facts,
the selected packet, birth/lifecycle, slow writes/file checks, stale clocks and
pending/unknown tokens fail closed without another acquisition or unlink retry.
Final receipt/marker/seal checks also read the original current cleanup phase.
The special original `RestartInputs.retire(..., before_discard=...)` callback
repeats this fence after its inner observation CAS immediately before discard.
That deliberate native read may advance only its accepted sequence; the native
birth/lifecycle and every other selected reader fact remain pinned.

The v3 manifest records `unlinkPolicy: original-source-16-unlinks-250ms` beside
the v2 immutable-file ownership declaration. Final and retirement versions match.
Default held v1 and closed-file v2 paths retain their original behavior. Cold
scope validation reads all three versions and refuses a v3 plan relabelled over
a v2 receipt. No file, byte, nonce, native-age, input or catalog limit is raised.
The complete warm v3 join remains unqualified pending its measured full rerun.

The actual component application owner plus v3 archive/fence, existing archive,
typed plan and actual Pico factory selections passed 32 cases in 68.762 seconds.
The new counterexamples retain originals on either frozen-clock late CAS,
post-intent file-check delay, changed/retired HTTP phase, changed accepted native
facts, final-guard mutation, acquisition age exceeding its original deadline,
and phase change after the actual inner RestartInputs observation CAS. Its
17-file positive performs five full native-production-seam acquisitions and
new original phase queries for every unlink; it never fabricates a later native
timestamp from HTTP. No complete 2623-file warm archive result follows from
this smaller actual host component proof.

The full warm v3 diagnostic then copied all 2623 originals and multipart manifest
in 470.022 seconds of archive time. The first 256 admitted retirements needed a
further 120.037 seconds: each copy and each retirement reopened the entire copy
set. Following explicit test coordination, the single host diagnostic was
controlled-stopped at 393 retirements (exit 143), without whole success. Its
remaining original files, complete immutable copies, manifest and incomplete
retirement ledger remain private and untouched. They are not adopted by a new
owner, retried or qualified as a sealed complete archive. A separately recorded
private abort report preserves the measured counters. No registered test bound
was changed. A concurrent narrow source regression was reported during this
measurement; no source-age failure was reported before the controlled stop.

Archive/plan v4 addresses that measured repeated byte scanning explicitly.
Every new copy still gets the unchanged complete `ClosedOriginalFile` read
window: original held directory, actual nofollow FD/kernel alias, full physical
stamp, bytes and safe alias closure. The complete archive byte pass remains
before any original retirement and before the last native source acquisition.
Each actual unlink, including the inner RestartInputs CAS/discard boundary,
fully rechecks its own original/copy, original manifest part and manifest root.
After the final CAS it also checks the entire actual held-directory inventory
and every copy's original device/inode/UID/mode/link count/size/mtime/ctime.
The source fence runs after those checks and uses exactly its pre-intent frame.
No native source refresh is permitted after that unlink's durable intent.

Between those complete byte passes, unchanged *other* copies are not reopened.
The physical-inventory pass is explicitly not a new read of cached bytes. Each
cached immutable bytes object/owner is independently pinned; its full stamp,
original digest and byte count belong to an immutable admission tuple and a
separate digest chain. Mutating a cached value/digest/stamp cannot change that
admission. Inventory enumeration resets only the kernel-verified original
directory cursor and uses nofollow stats relative to its held FD; replaced
parents, extra entries, symlinks and replaced/lost copies fail closed. Every
opened file window still performs its full original byte/FD/path checks.

The new final receipt gets its own full byte window and a complete physical
inventory before same-original source/phase freshness checks. Missing/replaced
copies cannot seal. The cold reader still performs the complete original byte
pass; a partial/uncertain warm attempt cannot be reconstructed or retried.
The v4 manifest declares
`copyVerification: full-current-copy-and-original-physical-inventory` alongside
the v3 source fence and v2 immutable-file ownership declarations. Legacy v1–v3
paths remain supported with their existing verification policy. No bounds or
source ages are widened. Host-handle finalization and the complete warm v4
measurement remain explicit outstanding closure work; public Chat stays partial.

The v4 physical-index/byte-window, retained v3 source-fence, existing archive,
typed plan and actual Pico cold-scope factory selection passed 41 host cases in
6.739 seconds. Its 32-original positive bounds the actual full copy-read windows
linearly while retaining complete passes and each current-copy/manifest read.
Counterexamples cover own/other copies, both manifest levels, extra paths,
original-directory replacement, in-memory bytes/digest/stamp mutation, inner
RestartInputs CAS corruption, late final physical inventory and lost or
identical-byte replaced copies during the final receipt. The full smaller
application-owner composition and full warm v4 measurement still need reruns;
these focused checks do not qualify either missing result.

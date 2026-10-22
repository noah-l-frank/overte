# Original Pico Chat application and archive closure v1

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

`ChatEvidenceArchive` holds original Linux directory/file descriptions, full stamps
and exact bytes. Each source is copied once into a newly created private evidence
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

# Phone original OS destination retirement

The separate `snapshotExportReadbacksVersion: 2` source retains the original
Save URI and adds `osDestinations`, a passive original MediaStore identity/byte
owner. Outer Snapshot-v5 and Android callback history-v2 remain unchanged.
Legacy readback-v1 can still acquire original host copies; it cannot establish
OS destination retirement. The complete Snapshot facade remains distinct
integration work. The separately installed consuming Share fixture and reader
are documented in [the receiver handoff](../../fixture/android-snapshot-receiver/README.md).

The existing native Save callback registers only its actual returned URI,
original resolver/context, actual file name and whether the original
`ContentResolver.insert` created it. No command accepts a URI, path, byte count,
desired hash or expected deletion result. MediaStore qualification reads its
actual row, provider UID, owner package, display name and original descriptor
device/inode. It independently reads and closes the original OS stream. The
original identity and acquired bytes/SHA remain bound to that export request.
A SAF-returned URI without proven new ownership remains red for deletion.

`remove-destination` uses an existing export request ID and one durable host
operation ID. Before sending one actual resolver delete, the source reopens
the original descriptor and bytes and verifies the retained tuple/hash. A
changed provider, owner, URI, inode or contents prevents deletion. The native
one-send intent precedes the call. A lost return never authorizes a second
delete: only a new original provider query and descriptor absence can resolve
it. Query errors or permission failures never mean absence. Source memory is
process-bound; a different process cannot adopt these responsibilities.

`inspect-destinations` accepts only a fresh resource nonce and independently
queries every owned original. `PhoneSnapshotReadbacks.require_os_retired(run)`
requires the newly completed inspection, all owned deletion intents, actual
fresh absence, no pending work and, after copy retirement, actual worker
termination. ACKs and an old successful inspection do not qualify cleanup.
The read-only actor gate allows inspection and rejects deletion. Existing
two/five/fifteen-second transport/source/stream bounds are preserved.

Private copy retirement now requires OS destination retirement first.
Fresh inspections remain possible after the original copy worker is closed;
bounded temporary inspection/deadline threads are separately tracked until
they actually terminate. They acquire absence only and cannot re-create an
owned destination. Reappearing OS targets remain red.

The guarded Java source is initialized only by the existing Phone-E2E plus
`--testScript` native gate. Normal builds keep their existing Save/Share path.
The actual Android Snapshot Java classes compile with prepared API 34 and
AndroidX Core. The ownership class runs against real host file identities,
streams, close failures and deletions in eleven counterexample scenarios;
eight strict reader tests check freshness, closed grammar, foreign identities,
missing originals, pending close and read-only actor enforcement. Host resolver
and URI fixtures do not execute MediaStore, SAF or a real Android permission.
No APK was installed and no device was used.

The same separate source includes `shareGrants` from the actual native
ACTION_SEND URI and actual chooser ComponentName/PackageManager UID. The
chooser callback still proves only selection. `revoke-share` accepts one
existing request and one retained operation ID, calls the real context URI
revoke once and independently checks the selected receiver and system chooser
UID grants. Fresh `inspect-shares` nonces are single-use; the read-only actor
can inspect but cannot revoke. `require_share_retired` requires a newly
completed original permission check. A missing selected receiver is never a
consumption proof. Private-copy retirement requires both destination and grant
retirement, and actual closed workers. The separately credentialed consumer
source must establish original consumption before permission retirement.

Private readback creation publishes the actual file identity under the same
owner lock as creation. Concurrent readers can observe an absent planned
path or its acquired original identity; a newly created file is never exposed
before its original file key is retained. The host publication test delegates
to the real filesystem and pauses immediately after actual creation. Original
copy, observation, close and retirement bodies run concurrently. Restoring the
former creation-before-lock ordering is rejected in that same window. This
qualifies E2E helper synchronization only, not Android provider behavior.

The native OS queue permits a fresh original absence inspection after an
unknown IOException from the already-issued one-send deletion. Only that
retained `delete-uncertain` state is resumable; identity, permission/runtime,
stream-close and provider-query failures still invalidate the source. A second
operation ID never authorizes another deletion, and an ignored delete remains
present/red. This does not treat a lost ACK or thrown request as success.

The shared private-file helper includes the exact atomic file-publication fix
and deterministic mutation counterprobe from parent commit `0791d14be9`.
Creation and captured fileKey now share the same existing observation lock.
The receiver additionally reads actual original private bytes only after
identity/mode/link/size/SHA checks, closes the read and verifies identity again.

Local verification for the consuming-receiver packet: 72 explicit Snapshot
readback/publication/file/OS/grant/consumer tests passed, including eleven
actual receiver file/stream/thread scenarios and twelve strict consumer reader
and transport tests. The actual TestScriptingInterface readback method compiles
against Qt6 and admits only the new closed ID routes. All Snapshot Android Java
classes compile against prepared API34+AndroidX; the standalone receiver also
runs actual javac+d8+aapt2 packaging. The emitted APK is unsigned/uninstalled.
No real Android grant, chooser, MediaStore/SAF or native app execution is
claimed. Global feature-count/profile/source-pin updates remain parent-owned.

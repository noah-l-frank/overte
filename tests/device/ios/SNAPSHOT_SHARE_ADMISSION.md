# Independent Snapshot Share archive and embedded extension code

`IOSSnapshotShareAdmissionRuntime` and `IOSSnapshotShareAdmissionOwner` admit
the already running, separately bound standalone Share archive application.
The selected archive and independently observed installed application must
contain the exact same complete byte forest, including the embedded Share
extension, its executable, signature and provisioning files. This admission
does not choose a system Share row, start an extension, receive a capture,
import an original, prove process absence or enable complete Snapshot support.

The selected final IPA is read unchanged without extraction. Its app declares
the closed `share-archive` role, contract version 1 and file sharing. Exactly
one actual embedded `.appex` must provide its own Info.plist, executable,
`XPC!` package type, app-derived `.receiver` bundle identifier and
`com.apple.share-services` extension point. The app and extension must name the
same explicit App Group. The actual extension byte forest receives a separate
digest and remains part of the complete containing app digest. Competing,
nested, missing, foreign-role or malformed extensions fail before SDK input.
This is structural byte identity; it does not validate Apple signatures,
provisioning entitlements, installation or successful App Group access.

The existing descriptor-relative native forest reader has two closed
compile-time profiles. The unchanged default is Photos. Only the standalone
Share archive executable sets `OVT_SNAPSHOT_SHARE_ARCHIVE=1`; its panel exposes
only `snapshot.share.companion.nonce`, `.clock` and `.identity`. Its distinct
`snapshotShareCompanionObservationVersion` original reports the
`share-archive` role and writes `snapshot-share-companion-{clock,identity}.json`.
The Share target has no Photos framework or permission observer. No host or
application parameter can select an arbitrary profile. No product build entry
is changed. Both profiles now reject failed file/directory close operations
during their exact native installed-forest census.

The Share owner reuses durable normal UIKit nonce inputs, one-send inspection,
unchanged AFC bytes, independent native and host clocks, candidate/process/SDK
continuity, selected archive inode and immutable private originals. Its owner,
source frame and original-file namespaces are separate from Photos. A lost
button return reads the same original without another inspection call. A
changed source lifetime, PID, archive, driver bundle or session generation,
including an integer-to-boolean substitution, blocks subsequent inputs.
Historical archives read only the actual retained originals and selected IPA;
they do not touch the SDK or reserialize a Photos source into a Share source.

All new Share artifact, observation, code-admission, source-frame and
`ios-snapshot-share-code` owner/frame/original contracts write/read version 1.
Default Photos fields, versions, controls, filenames and historical readers
retain their original grammar. Each source rejects the other role/schema.

On 2026-10-26, the final explicit host selection passed 27 tests in 10.355
seconds: seven new Share admission tests, sixteen existing Photos admission
tests, one existing Photos artifact test and three real Photos factory/context
tests. They use actual ZIPs, selected archive and installed host files, private
CAS/immutable originals, HTTP/AFC codecs and explicit UIKit/OS/native producer
models. Negative cases mutate actual extension executable/signature/provision
bytes, add installed nodes, select wrong/extra/nested extensions, change App
Groups, replace the archive inode, lose an actual modeled return and substitute
schemas. No compiler, CMake configuration, device or laboratory was used.

The next Share stages still require normal system presentation/selection and
cancel inputs, candidate-bound live extension scope, original archive import
and bounded AFC byte acquisition, native client completion, actual extension
process absence, owned App Group/Documents retirement and repeated quiet
cleanup. Their completion cannot be inferred from this code-admission receipt.

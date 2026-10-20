# Original Phone Graphics PNG files, version 1

`PhoneGraphicsImages` preserves original acquired PNG bytes in the existing
private artifact directory. It renders or resamples nothing, accepts no expected
feature state and creates no current product measurement. The complete Graphics
source/fixture/input/publisher/cleanup owner remains missing; no new capability
is advertised by this component.

The constructor binds the actual candidate/process/session context, run,
primary/actor role and explicit restart stage 0/1. Its caller supplies the already
prepared canonical private artifact root, existing source/binding/lock guard and
a durable intent callback. The callback must atomically persist/read back each
record before returning. All live operations require that guard, including
the existing shared native-source lock held by their owning coordinator.

The record is closed: `graphicsImageVersion:1`, actual `binding`, `runId`, `role`,
`stage`, scoped `ticket`, complete original v2 `capture` packet, direct `name`,
`phase` and `file`. The filename is exactly
`graphics-<run>-<role>-<stage>-<original-capture-nonce>.png`; the original native
capture metadata and its original native PNG filename are not rewritten.
Ticket/run/role/stage are ownership labels, not decoded feature facts. The
separate measurement join must independently decode actual current challenge
pixels before a full adapter can publish the image.

Three persisted phases make interruptions reviewable. `planned` has `file:null`
and is stored before opening anything. The file is created with exclusive,
no-follow admission and owner-only permissions; existing files are never
overwritten or adopted, even if their bytes equal the acquired image. `opened`
stores actual filesystem device/inode before writing bytes. `saved` is stored
only after original-byte write/flush/fsync, separate descriptor/path identity
checks, fresh reopen and original encoded/RGBA hash validation. No source stamp
is retimed. A lost saved-return is recoverable by checking the same original
file; a partial/empty/unknown file cannot become completed evidence.

Reads require the original device/inode, regular single-link owner-only file,
matching private canonical parent, native size bound and exact original PNG/
decoded-pixel hashes. Replacement, in-place changes, symlinks, hardlinks, missing
files or exposed permissions fail. `absent` is a separate actual filesystem
query, not an unlink ACK. The component intentionally has no arbitrary unlink
or repair route. Unknown or partial ownership must stay explicit in the future
source owner's cleanup journal. Complete saved PNGs are deliberate private run
evidence and may be retained after native image leases retire; they do not
authorize forgetting incomplete source ownership.

Each operation has a five-second maximum budget, including decode, callbacks,
file IO and binding guards. A shared monotonic floor also catches regression
across nested readback and callback boundaries. `archive(root,record)` performs
only historical private-file/byte validation with no SDK, input, repair or live
candidate assumption. It returns the original old bytes and changes no timestamp.
Historical reading cannot qualify a new feature observation or ticket.

Fourteen device-free cases use real private host files and persisted intent
records, with explicitly synthetic original render packets. They cover exact
byte/inode preservation, three-phase ordering, foreign/matching preexisting
files, failed intents, empty partial files, lost saved-return recovery, changed/
replaced files, symlink/hardlink/permission refusal, foreign role/stage/candidate/
process, independently observed absence, decode/guard/clock budgets, historical
readback and wrong original pixel hashes. These verify test/file logic only.
No native client, compiler, build, installation or device was used.

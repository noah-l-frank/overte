# One physical Tablet, independent observer admission

`admit_existing_tablet_observer` reads a separately running observer's existing
SDK target/session and compares its actual binding with the original physical
binding retained during genuine Primary preparation. Every binding field must
agree: source revision, artifact, session, generation, target fingerprint and
actual process ID. A different device/session is not a private Tablet witness.

The function uses `IOSScriptRuntime._existing`, the real installed binding's
`record()` and original DVT/source `continuity()` reads before/after. It never
calls `_sources()`, `verify()`, `bind()`, a native verification command, app
launch/Stop or SDK creation/deletion. Literal version 1 requires byte-semantically unchanged installed records.
Version 2 permits the actual outer InstalledAdapter verification to advance
its original bundle-observation sequence/nonce/capture while preserving the
same native observation instance, prepared epoch, bundle bytes, SDK/source,
process and complete remaining installed record. Same-sequence rewrites,
rollback, changed native births and reused nonces fail closed. The measured host epoch/monotonic bracket must be less
than 1.5 seconds and cannot move backwards. Actual host PID is retained; no
private selector is serialized. The pure historical validator has no SDK or
mutation callbacks and reads the genuine original installed schema.

This is SDK/candidate continuity metadata, not a current native bundle/view
observation or proof that two workers are independent. The enclosing run must
retain the actual prepared Primary binding and separately qualify its original
worker identity, each worker's own fresh queries/source births/PNG originals,
phase publication and final responsibility. A caller's expected replacement
binding or copied normalized Primary observation cannot fill those joins.

Both observers intentionally use the same physical client/session. Primary
alone owns its one normal app Stop and final SDK deletion. Actor owns its own
reader/query/file/worker resources, independently observes the same actual old
PID's OS absence, and never creates/deletes the shared SDK or stops the app.
Any future terminal protocol must explicitly retain this identity instead of
pretending the Tablet is visible on a second remote avatar/device.

Each separate CLI operation retains its own actual host PID and read-only
admission. The initial bootstrap keeps its original host and native birth;
a Python subprocess is not the application's native lifetime. A new current
admission must follow the original immutable native installation/process.
Acquisition version 2 embeds this exact current admission before the first
native query and binds its actual host PID and original acquisition clock.
This is distinct from any later installed binding file update.

The admission DTO writer is `tabletWebObserverAdmissionVersion: 2`, reads
literal versions 1 and 2, registry key
`ios-tablet-web-observer-admission`. This prerequisite does not advertise full
Feature 7 capability. Host tests use actual private installed binding files and
read-only existing-SDK boundaries; no device action was performed.

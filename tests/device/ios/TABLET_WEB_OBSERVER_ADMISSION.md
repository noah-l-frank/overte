# One physical Tablet, independent observer admission

`admit_existing_tablet_observer` reads a separately running observer's existing
SDK target/session and compares its actual binding with the original physical
binding retained during genuine Primary preparation. Every binding field must
agree: source revision, artifact, session, generation, target fingerprint and
actual process ID. A different device/session is not a private Tablet witness.

The function uses `IOSScriptRuntime._existing`, the real installed binding's
`record()` and original DVT/source `continuity()` reads before/after. It never
calls `_sources()`, `verify()`, `bind()`, a native verification command, app
launch/Stop or SDK creation/deletion. Existing installed records must be byte
semantically unchanged. The measured host epoch/monotonic bracket must be less
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

The admission DTO is `tabletWebObserverAdmissionVersion: 1`, registry key
`ios-tablet-web-observer-admission`. This prerequisite does not advertise full
Feature 7 capability. Host tests use actual private installed binding files and
read-only existing-SDK boundaries; no device action was performed.

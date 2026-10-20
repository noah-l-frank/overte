# Private Script fixture storage, version 1

This E2E-only source stages the four controlled Script fixtures; it never loads
code, chooses a picker item or emits an execution verdict. Normal file selection,
actual engine/require history and advancing entity effects remain separate.
C++ is **uncompiled**, and all device behavior is **unqualified**.

Every request is bracketed by separately acquired original native clocks,
including HTTP/AFC on iOS. The actual request timestamp cannot predate the
first clock; the final clock cannot regress and must establish capture
freshness. Neither host UTC nor the receipt's own capture time qualifies it.
Clock reads and process guards share the existing five-second monotonic
deadline. A late initial clock prevents sending, and a late final clock leaves
the receipt cursor and durable cleanup intent uncommitted. Uncertain mutations
are never replayed; normal independent file readback remains mandatory.

The `feature-script-files` command has exactly `schemaVersion:1`, a fresh
`commandId` (32 lowercase hex, `ios-` prefix on iOS), `action`, `operation`,
`runId` (32 lowercase hex) and `ownerToken` (64 lowercase hex). Operations are
`stage`, `observe`, `release`. Stage additionally carries exactly four `files`
entries, each canonical base64 of 1..8192 original bytes:
`script.js`, `companion.js`, `script-bundle/main.js`,
`script-bundle/companion.js`. No caller-supplied directory, arbitrary relative
path, desired result, filename pattern or load/stop action is admitted. JSON
is bounded to 49152 bytes. The iOS fixture validates this same closed schema.

`Test.featureScriptFiles()` requires the default-off feature instrumentation,
explicit `--testScript`, a valid lifecycle observer and the existing private
results directory. It serializes on its owning native thread. The Unix source
opens that actual canonical directory with no-follow directory descriptors,
reserves `feature-script-<runId>` exclusively with `mkdirat`, and persists its
private `.owner.v1.json` before creating fixtures. The manifest records the
opaque ownership token, run and hashes computed from the supplied original
bytes. Files use exclusive no-follow creation, private modes and fsync. An
existing directory is never adopted by another Stage, overwritten or removed.
No non-Unix insecure fallback exists.

Read/release re-open the actual private directory and manifest, require the same
opaque token and exact bounded inventory, and refuse foreign entries, symlinks,
shared hardlinks, nonregular files, changed original hashes and unsafe modes.
Reads are nonblocking before checking file type and compare descriptor metadata
before/after. Actual directory descriptors must still match their path entries.
Observe returns original base64 bytes and hashes read from files, not the
manifest's expected hashes. Missing known files are explicit `exists:false`
rows. Missing roots produce `exists:false,files:[]`; OS errors never mean
absence. Only a fresh native observation proves that absence.

The original private `feature-script-files.json` response contains
`schemaVersion:1`, `requestId`, native `instance`, advancing `sequence`,
`requestedEpochMs`, `capturedEpochMs`, actual `processId`, `runId`, `operation`
and `source`. Stage/release `source` contains only `performed:true` on success.
Observe of a present root contains `exists:true`, its actual native `directory`
file URI and exactly four `files` rows. Present files have `name`, `exists:true`,
`bytes`, `sha256`, `base64`; absent files have `name`, `exists:false` only.
An unavailable/rejected operation cannot become an acknowledged success.
The native owner caches an identical latest request without replay or retiming.

`NativeScriptFiles` checks original bounded response bytes, request/run/operation,
PID, native instance/cursor, native request fence and time, as well as each
actual file's content/hash/size. At most five seconds/51 original reads are
allowed, counting send/transfer time. Writes are never replayed after an
uncertain receipt. iOS uses source-native time fencing, avoiding a fabricated
host/device clock equality; its canonical installed-code gate remains mandatory.

`OwnedScriptFiles` persists a private compare-written ownership intent before
Stage. It generates the controlled originals through the existing fixture
module and separately reads every staged file, comparing the original bytes.
Its returned path is the actual native observation. Stage ACKs, missing files
and hash-shaped claims are insufficient. Release requires the same persisted
binding, native acknowledgment and a separate fresh absence read before
retiring intent. Errors retain ownership. Partial writes/removals and foreign
content therefore fail closed; they are not silently marked cleaned. A native
I/O failure while first persisting the ownership manifest, or after removing
it during final directory retirement, can require operator repair of that
reserved root; the host intent must be retained and the run must fail.

The isolated platform branches now supply internal `_script_files()` factories.
Phone uses its original Appium/private run-as channel with installed-APK and
PID/start/session guards. Pico uses its original candidate/OpenXR channel and
same normal Script context. iOS uses original HTTP/AFC bytes and the actual
normal-input session/fingerprint/process continuity closure, explicitly labelled
`NATIVE_UI_COMPONENT_ONLY`; its canonical binding refuses this method. Platform
general cleanup reaches original teardown and then rejects persistent file
intent. It does not blindly release files that might belong to a running engine.

Process/session binding currently cannot be rebound automatically after an app
restart. The full journey coordinator still needs an explicit verified restart
handoff, dialog and engine cleanup before file release, real advancing effect
observations and the independent observer journal. Never delete a running
script's files as a substitute for Stop/absence. None of these storage methods
advertises a full feature capability.

Nine host tests exercise actual Python ownership/transport/probe dispatch with
simulated native filesystem boundaries reading real temporary fixture bytes.
Counterexamples cover ACK-only staging, changed/missing content, ignored
cleanup, foreign context/manifest, stale/foreign/incomplete replies, partial
reads, lost guards and malformed closed requests. They prove control logic
only, not the native filesystem implementation or product/device behavior.

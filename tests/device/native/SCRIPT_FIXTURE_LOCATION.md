# Original Script fixture location, version 1

The existing fixed `feature-script-files` channel additionally accepts the closed
read-only operation `locate`. Its schema-1 command contains only `schemaVersion`,
`commandId`, `action`, `operation`, `runId`, `ownerToken`. It accepts no expected
path, existence, bytes, effects or verdict. Existing stage/observe/release wire
formats and file ownership v1 remain unchanged. Unsupported older producers fail
the new location requirement; an empty/missing result never means absence.

The original native source is exactly
`{locationVersion:1, exists:<boolean>, directory:<original file URI>}` inside
the existing request/PID/native-birth/sequence/clock envelope. `PrivateScriptFiles`
derives the URI from the actual canonical private results directory and actual
run leaf. The host never guesses an Android sandbox path. Location does not
create directories/files, change code/bytes, load execution, stop execution,
release ownership or create a tablet.

Absence requires actual `openat` failure with `ENOENT` and unchanged original
base identity. Permission/unknown errors are unavailable. A present root requires
the existing private, unshared, nonsymlink ownership manifest with the exact
run/token/hash inventory and allowed root entries; base/child identities are
rechecked. A foreign/unowned/unsafe root cannot become absent or be adopted.
Location presence alone does not verify fixture contents. Existing independent
`observe` readback still checks all four actual file bytes/digests before use.

`NativeScriptFiles.request` retains a deep copy of the last fully validated
original packet in `last_packet`. It clears that slot before every request and
on failed/ignored acquisition cannot return old data. Accepted original capture
clocks cannot regress within one getter instance. It retains existing
one-send request IDs, five-second getter bound, current native clocks, candidate/
PID/session guards and private-safe errors. The Phone read-only command allowlist
admits exact observe/locate shapes only; stage/release remain forbidden there.

`OwnedScriptFiles.reserve(run)` persists the existing strict private owner intent
without native requests or physical fixture creation. `stage_reserved()` makes
one exclusive native stage attempt and separately reads actual bytes. A full
coordinator must persist its stage-issued phase first and never replay uncertain
staging. Native exclusive creation prevents overwrites; original ownership stays
on error. Existing `stage(run)` composes these two methods. `locate()` scopes an
original query with the current owned token. Release continues to require an
independent absence query before discarding its original private intent.

Phone `_script_measurements(..., read_only=True, fixture_state='absent')` uses this actual native
location and rechecks absence before each fresh execution/UI/service/lifecycle
acquisition. Absent reads require non-repairing admission before any SDK or
native request. It returns their actual six fields: retained pending managers,
engines, Boxes or open UI cannot be replaced by baseline constants. The normal
`present` mode keeps full original-byte verification. Both modes use the same
actual native birth and directory. Durable primary/actor histories can cross
reserve/stage/release within the same original process without reset.

After actual release removed the file-owner journal, an explicit `retired_owner`
may provide the original frozen private cleanup scope for **absent reads only**.
Its full context/run/hash shape must still match; a current file owner blocks it
at construction and throughout acquisition. It supplies only the old scope/token,
never current evidence: a fresh native locate query must prove actual absence.
The full coordinator must freeze this original record before release in its own
versioned cleanup journal. Ordinary constructors never implicitly adopt it, and
nothing is recreated or restaged by a read.

[The file/source join](../ios/SCRIPT_FEATURE_SOURCES.md) combines the
original file envelope with all four current original packets and produces the
physical resource inventory. The coordinator still needs to persist its file
cursor, integrate normal input/restart/HTTP/independent publisher and retire all
journals only after complete cleanup. No full feature capability is promoted.

Twenty shared file-source cases (nine new), eight Phone factory cases and
eight file-scope joins run without devices. They cover actual location/absence,
private reservation, original byte readback, wrong/missing provenance, ignored
queries, exclusive staging, retained ownership and baseline continuity across
one original fixture lifecycle. The actual JavaScript dispatch is executed with
synthetic native boundaries. C++ instrumentation remains uncompiled and all
three clients remain untested on devices.

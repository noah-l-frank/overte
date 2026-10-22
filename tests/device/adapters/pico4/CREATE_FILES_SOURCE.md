# Explicit Pico Create JSON and original export storage v1

This is a source component for incomplete feature 4/14. The full Create
capability remains disabled. Ordinary picker/export input, original callback
retirement, domain/peer/stereo effects, PolyVox and permission recovery still
need their full coordinator. The isolated Qt5 Core harness compiles and tests
the actual storage header and extracted native role method; the complete Pico
application and devices remain unverified.

The existing `feature-script-files` private transport now accepts the **explicit
Pico-only** `sourceRole: "create-json-v1"`. The legacy Script command, Script
root admission, four Script filenames and Script response shape are unchanged.
The inherited Python transport shares only bounded exchange and original
nonce/process/clock/cursor checks. The explicit Create subclass validates its
own exact request, role/ticket response and original file metadata.

Commands have schema version 1, fresh `commandId`, exact `runId`, original
`ticket`, private `ownerToken` and `operation`. Stage adds only
`files: {"entity-import.json": BASE64}`; release adds `exportSha256`, either the
separately acquired original output digest or an empty string when absent.
Observe and locate carry no expected result. The complete command is bounded
to 16 KiB. It remains on the existing private controlled debug channel; the
general HTTP fixture does not gain Create file-write authority.

`Test.featureScriptFiles` dispatches this role only under the dedicated feature
test build and Pico configuration. The native method additionally checks the
current application thread, existing nonempty lifecycle, explicit `--testScript`
and private result root. Its bounded 512-command cache records uncertainty
before the one storage request. Any identical previous nonce returns the exact
original packet even after another role reads; changed requests with the same
nonce fail. Exhaustion fails without evicting old evidence or retiming results.

The descriptor-safe storage reuses the existing Script filesystem primitives
through a narrow friendship. It never admits a Script root or relaxes Script
validation. Each exclusive 0700 root is named
`feature-create-RUN-TICKET`; its original 0600 manifest authenticates role,
run, ticket, owner and input hash. Staging persists ownership first and writes
only the controlled DataVersion 3 entity-JSON **input**. The owner separately
verifies the original native input bytes against the immutable common fixture.

Storage never creates `export.json`. The ordinary product Save dialog must
write that file later. Readback preserves actual bytes, digest, device/inode,
mode and nanosecond modification/change times. Original output may have the
product's 0600 or 0644 mode inside the inaccessible 0700 root; no chmod or
rewriting changes original evidence. Inputs must retain 0600. Symlinks,
hardlinks, foreign entries, oversize files, noncanonical roots and changing
identities/metadata fail. Files are bounded to 8 KiB input and 32 KiB output.

The host owner persists the original input bytes/hash, candidate/process/session,
run/ticket and private token before staging. It records `stageAttempted` before
the sole mutation. A lost response can recover only through separate original
readback; it cannot restage. Export acquisition records the actual output hash
but does not judge its semantics: the common Create evidence parser still
requires the real DataVersion 0 model, original model ticket and distinct texture
ticket. An invented reference or staging ACK cannot establish an export.

Release is allowed only after the future coordinator proves normal picker and
callback retirement plus its quiet window. Unknown or changed export bytes
retain ownership. Native release validates every original before unlinking,
then a separate original absence query must succeed before host retirement.
Partial stage/cleanup remains authenticated and observable. An ignored release,
stale/foreign ticket, candidate, process, nonce, role, cursor or capture time
cannot clear the journal.

Selected verification uses `test_create_files` and the existing native Script
file/feature-source counterexamples (47 Python/Node cases). The separate
`test_create_files_native.py` compiles only Qt Core, the original storage header
and original extracted role method, with substituted application lifecycle
holding. It exercises actual original bytes, exclusive staging, authenticated
release, input tampering, symlink/hardlink/foreign-file rejection, real process
and native clocks, retained original nonces and bounded-cache exhaustion. It
launches no application, target, device, service or installer. The existing
`normal-create` suite also imports the six new pure Python/Node role cases;
the compiler test remains explicitly selected.

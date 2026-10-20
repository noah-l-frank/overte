# Original Script manager display, version 1

`ScriptManagerStatus.h` passively adds optional `manager` metadata to the
existing `scripts.from-file` row in the existing Script file UI observation.
It is enabled only with `OVERTE_E2E_FEATURE_TESTS` and `--testScript`, on the
original GUI thread. No extra command, input handler or error setter is added.
The original QML status Label receives only a local `scriptStatus` id; its text,
visibility, bindings, signals and user behavior are unchanged.

The reader walks at most 128 parents/contexts, locates the actual `RunningScripts`
root via its original QML `root` id and requires its actual context base URL to
equal independently configured `PathUtils::qmlUrl` for
`hifi/dialogs/TabletRunningScripts.qml`. It checks the original button/Flow/layout
ancestry and at most 128 direct layout children, selecting exactly one original
`scriptStatus` id in that same context. It reads original root `status` and the
separate Label `text` and effective visibility. Visibility also requires finite
nonempty geometry with its center in the actual window/clipped ancestor bounds,
all ancestors visible with opacity above 0.01, and the same original window.
The ancestor walk is bounded to 128; no assumption that a positive property
alone establishes displayed text is made. It never searches for expected
text, calls a QML handler, assigns a model or manufactures an error category.

Unavailable/wrong/ambiguous sources return exactly
`{managerSourceVersion:1,available:false}`. They cannot qualify a complete feature
observation. Available metadata contains exactly those two fields plus
`componentSource`, `statusText`, `labelText`, `rootVisible`, `labelVisible`.
The source is the actual QML context URL; both texts are original, bounded to
8192 UTF-16 units natively. Host readers also enforce 8192 characters and permit
only printable text or tab/CR/LF. Both visibility fields are actual booleans.
Raw text/source URLs stay on the existing private observation channel and must
not be emitted as public results, logs or artifact names. A composed feature
adapter publishes only the category established by independently joined facts.

`script_manager_status.manager_status(snapshot)` requires the source extension,
ready original full inventory and one actual manager carrier. It returns the
original metadata unchanged. `missing_error(snapshot,url)` additionally requires
the root and actual Label to be visible and agree, and the displayed full owned
missing URL with the original QML failure prefix. It preserves the actual
optional error suffix. It does not invent `NotFound`: a real current fixture404
and the original native callback/status, frozen input barrier and independent
execution/effect/peer/cleanup facts remain mandatory separate joins.

The owning existing IO transport must acquire a fresh nonce/cursor, actual
PID/birth/candidate/target and original clock within its existing deadline.
This helper never retimes a snapshot or substitutes host UTC for native time.
It adds no new wait or timeout. Old producers without optional metadata still
support existing picker inputs, but the complete display reader refuses them.
Pico/iOS full-inventory parsers and Phone's closed file UI parser must explicitly
accept only this optional metadata on `scripts.from-file`; unknown rows/fields
retain their existing refusal. All three product bindings remain source-only.

Nine host cases cover original versus broken display bindings, hidden pages,
foreign URLs, unavailable/missing sources, duplicate/closed inventories, malformed
native properties, old optional compatibility and caller-copy isolation. One
executes the actual QML error handler under Node; it proves JS/test semantics,
not Qt rendering. C++ is uncompiled and no device behavior is claimed. This does
not register a complete Scripts feature triple or physical acceptance.

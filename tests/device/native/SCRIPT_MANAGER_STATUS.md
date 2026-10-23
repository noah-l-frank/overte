# Original Script manager display, version 2

`ScriptManagerStatus.h` passively adds optional `manager` metadata to the
existing `scripts.from-file` row in the existing Script file UI observation.
It is enabled only with `OVERTE_E2E_FEATURE_TESTS` and `--testScript`, on the
original GUI thread. No extra command, input handler or error setter is added.
The original compact QML status Label retains its `scriptStatus` objectName.
The original error signal also retains its actual full URL and actual signal
epoch in passive root properties. No requested URL, preferred error or expected
result enters the native getter; displayed text and normal input stay unchanged.

The reader walks at most 128 parents/contexts, locates the actual `RunningScripts`
root via its original QML `root` id and requires its actual context base URL to
equal independently configured `PathUtils::qmlUrl` for
`hifi/dialogs/TabletRunningScripts.qml`. It traverses at most 4096 visual items
and 128 levels inside that root, selecting exactly one `scriptStatus` objectName
or retained old id with a declared object identity in that exact QML context.
This admits the product's new Flickable hierarchy without adopting a foreign
inline object, duplicate label or matching text elsewhere. It reads original root `status` and the
separate Label `text` and effective visibility. Visibility also requires finite
nonempty geometry with its center in the actual window/clipped ancestor bounds,
all ancestors visible with opacity above 0.01, and the same original window.
The ancestor walk is bounded to 128; no assumption that a positive property
alone establishes displayed text is made. It never searches for expected
text, calls a QML handler, assigns a model or manufactures an error category.
The file-input carrier must belong to that original component context and be
the unique `scriptFromFile` child of its declared `loaders` Flow under declared
`content`. A foreign button elsewhere, a dynamically inserted button or duplicate
carrier cannot borrow a valid root's manager evidence.

Unavailable/wrong/ambiguous sources return exactly
`{managerSourceVersion:2,available:false}`. They cannot qualify a complete feature
observation. Available metadata contains exactly those two fields plus
`componentSource`, `statusText`, `labelText`, `rootVisible`, `labelVisible`,
`errorUrl`, `errorEpochMs`. The latter two retain the original signal's full URL
and epoch; an absent error starts with empty URL/zero epoch. They never retime
an old error to the current acquisition. Private v1 observations lack this
causality and cannot be resumed or relabeled as v2. Preserve owned journals and
finish them with matching old instrumentation rather than silently migrating.
The source is the actual QML context URL; both texts are original, bounded to
8192 UTF-16 units natively. Host readers also enforce 8192 characters and permit
only printable text or tab/CR/LF. Both visibility fields are actual booleans.
Raw text/source URLs stay on the existing private observation channel and must
not be emitted as public results, logs or artifact names. A composed feature
adapter publishes only the category established by independently joined facts.

`script_manager_status.manager_status(snapshot)` requires the source extension,
ready original full inventory and one actual manager carrier. It returns the
original metadata unchanged. `missing_error(snapshot,url)` additionally requires
the root and actual Label to be visible and agree. A compact basename or the
older full-URL label is accepted only with the independently measured exact
full `errorUrl` and signal epoch at/after the frozen input barrier. The composed
reader additionally rejects a signal after its actual UI capture and still
requires the matching native failed callback and actual owned HTTP404 receipt.
A same-basename foreign/stale URL is not identity. It preserves the actual
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

Focused host cases cover original versus broken display bindings, hidden pages,
foreign URLs, unavailable/missing sources, duplicate/closed inventories, malformed
native properties, old optional compatibility and caller-copy isolation. One
executes the actual QML error handler under Node; it proves JS/test semantics.
The existing small offscreen Qt component harness compiles this original native
header and loads the original QML to check real label/control identity and
visibility, including foreign carriers. This is host component verification;
no complete client compilation or device behavior is claimed. This does
not register a complete Scripts feature triple or physical acceptance.

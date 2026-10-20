# Existing-session Phone observation, version 1

An independent target observer must not repair the condition it measures.
`existing_session(selector)` therefore reads the existing private session,
requires its current target fingerprint and a bounded safe session id, checks
the selected installed APK bytes, and performs only the existing SDK
`GET /session/<id>` liveness query. It repeats original session/configuration and
installed-candidate checks afterwards. It never calls `ensure_session`, deletes
or rewrites state, creates a session, installs, activates or launches the app.
Missing, replaced or dead sessions fail with preserved ownership. SDK errors
are replaced by a fixed private-safe error, without raw endpoint/selector text.

The internal `normal_feature_runtime(..., read_only=True)` uses this admission
instead of session repair. Its original actual foreground/PID/start-time,
generation, session and target checks remain required. This mode does not
provide a restart handoff or adopt a replacement process. The independent actor
must handle a separately verified new process through its own explicit source
transition. It cannot reset source history simply because an input requested a
restart.

`_native_feature_observer`, `_script_execution_observer` and `_script_file_io`
accept the same strictly boolean `read_only` option. Read-only native transports
admit only the existing exact native-feature getter, Script-execution getter
and Phone Script-file-UI **observe** request. The joined
[Script reader](SCRIPT_MEASUREMENTS.md) additionally permits the strict native
fixture **observe/locate** requests with the original owner token. They reject UI input, fixture
stage/release, lifecycle commands and desired-state fields before dispatch.
Request schema/type/nonce fields remain strict. The file IO object's input
methods cannot use this transport to deliver a click. Native diagnostics in the
runtime use their original fixed read-only diagnostic command. Native getters
may write only their ordinary private observation output; they change no
functional state.

The SDK liveness request retains the shared WebDriver 30-second transport bound
and bounded response. Native acquisitions retain their existing five-second/
51-read checks, independent Android epoch and original before/after continuity
guards; the enclosing runner's module/process deadline still applies. This
adds no retry, unbounded wait or timeout exemption. No SDK query failure is a
reason to create a new session. No cleanup mutation is performed by a reader.
Primary input factories retain their existing ordinary session behavior.

Eight joined device-free cases exercise existing-session original Script
reads, missing/foreign/unsafe state, dead SDK sessions, candidate replacement,
mid-query session replacement, forbidden mutations, attempted file-UI input
and process loss. All 138 Phone feature-adapter host cases pass. These use
synthetic SDK/ADB boundaries and confirm test logic only. The independent actor,
its private publisher provisioning and serialized original-command acquisition
remain to be composed; this source option alone is not actor evidence or a
complete feature capability. Devices remain untested.

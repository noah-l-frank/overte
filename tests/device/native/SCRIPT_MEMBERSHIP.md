# All-known Script manager membership, version 1

The public running-script hash is incomplete for cleanup: a normal
`ScriptEngines::loadScript` creates/adds its manager before the asynchronous
ScriptCache response, but inserts its running URL only in `onScriptEngineLoaded`.
No running row, callback or Box yet is therefore insufficient proof of absence.
This passive E2E source observes the original `_allKnownScriptManagers` set.

With `OVERTE_E2E_FEATURE_TESTS` and `--testScript`, the original successful
set insertion/removal increments a private membership revision. Duplicate calls
without actual set changes do not increment it. The original `loadURL` code,
immediately after assigning `_fileNameString` and before cache dispatch, records
that actual expanded URL, original `loadRequest.featureGeneration()` and actual
native assignment epoch under the existing observation mutex. It does not call
a loader, change a callback/ticket, cancel work, keep a manager running or invoke
its JavaScript heap. Unsupported/private URL forms make this source unavailable;
raw credentials, queries, fragments and inline source are not exported.

`ScriptEngines::featureScriptObservation` adds optional
`membershipSourceVersion:1` and `membership` to the original source. A complete
membership is exactly `{complete:true, revision, managers}`. Each row contains
exactly `instance`, `assigned`, `url`, `loadGeneration`, `assignedEpochMs`.
The instance is the original manager's independent required-module instance.
`assigned:false` explicitly means no observed native load URL assignment, with
empty URL/zero generation/epoch; it is not an unavailable getter default.
Otherwise the original typed URL/generation/epoch are preserved. This is load
membership/intent evidence, never execution success.

The native reader copies at most 128 original manager references under the
existing all-managers mutex, reads only small locked native metadata, and
rechecks the original membership revision. It holds no set lock while reading
manager metadata and never waits for a script-thread evaluation. Null/unsupported
sources, excessive membership, revision overflow or concurrent set changes yield
exactly `{complete:false}`. Partial arrays cannot qualify absence. The original
whole-source byte limit, nonce, native capture clock and process/lifecycle guards
remain in place. Narrow readers may still parse an unavailable optional extension;
full Phone measurements require it to be complete.

`NativeScriptObservation.read(..., require_membership=True)` requires this source.
It validates strict types, unique original instances, bounded revisions/epochs,
all original running engine instances belonging to the complete known set, and
immutable URL/epoch within an actual load generation. Genuine later native load
generations may advance the URL/epoch; set membership revision is independent.
Membership changes require an advancing actual revision, retired instances cannot
reappear, and source histories are bounded to 4096 observed instances. Native
capture epochs cannot regress. A required/previously complete source cannot be
silently dropped or replaced by incomplete/empty data.

Phone measurements are now **version 2**, reading only v2. All owned known
managers must exactly correspond to the actual eligible engine identities/URLs.
An owned pending manager with an empty running hash/service/effect source fails;
it cannot become a clean cancel/stop result. Version 1 was an internal live reader
with no persisted results, full feature producer or device qualification. Its
sole Phone factory is promoted to v2; there is no v1 full-area producer to retain.
The generic optional native-source contract still supports old narrow producers.

The [restart handoff](SCRIPT_RESTART_HANDOFF.md) reads v1 and v2. A v2 transaction
durably adds `membershipRequired:true`. Phone always creates/requires v2, checks
one matching owned known manager before shutdown and requires original current
known-manager absence throughout the new process's three-second quiet window.
Even a default/narrow constructor reading a frozen v2 record must enforce that
record's requirement; it cannot downgrade the proof. Strict Phone admission refuses
a v1 journal before native adoption and preserves it unchanged. No automatic
schema upgrade invents missing original proof. Other narrow source components
may explicitly retain v1 compatibility until their separate platform phase.

Ten native-reader counterexamples, seven handoff policy/pending-load cases, two
joined-measurement cases and three Phone wrapper cases cover pending work with
no public row, unavailable/old sources, history rewrites/reuse, late pending work,
quiet-window failure, ownership retention and forbidden journal downgrade.
Current focused totals are 28 handoff, 30 measurement and 145 Phone adapter cases,
all passing. These use synthetic native/SDK boundaries and actual private host
journals/files. Native C++ remains uncompiled and all clients remain untested on
devices. No full feature capability or physical acceptance is promoted.

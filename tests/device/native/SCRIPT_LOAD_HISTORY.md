# Original top-level Script load history, version 1

`native-script-load-history:1` extends the existing
`feature-script-observation.json` source with `loadSourceVersion:1` and `loads`.
The command remains the closed read-only `feature-script-observe` operation;
it accepts no URL, status, desired error, expected source or success value.
The default-off `OVERTE_E2E_FEATURE_TESTS` build option and explicit
`--testScript` remain mandatory. This source is **uncompiled** and **untested
on devices**; host simulations qualify only consumer logic.

The producer observes `ScriptManager::loadURL()`'s original ScriptCache
callback after retaining the actual manager and passing both existing live
request/completion guards. It records the callback's actual URL, `isURL`,
`success`, ResourceRequest/cache status and original load-ticket generation.
The native manager identity comes from its existing require/source observer.
It records before the existing error/loaded signals and never changes them.
In particular, the original failure branch may also emit `scriptLoaded` to
retain temporarily unavailable scripts. That signal, manager membership and a
successful input receipt cannot substitute for the actual fetch result.

`loads` has exactly `complete:true`, `instance:<32hex>`, `sequence` and
`events`. One native process owns the random source instance and immutable
append-only history across manager destruction. The sequence equals the
number of events, from 0 through 256. Each event is exactly:

| Field | Original meaning |
| --- | --- |
| `sequence` | Contiguous one-based callback sequence; reads do not advance it |
| `eventId` | Fresh native 32-hex event identity, unique within the source |
| `managerInstance` | Actual manager's 32-hex native require/source identity |
| `url` | Original full callback URL for URL input; empty for inline input |
| `loadGeneration` | Original live load ticket's positive generation, at most 2^53−1 |
| `isURL` | Original callback boolean; false only for `Inline` |
| `success` | Original callback boolean, true exactly for `Success`, `Cached`, `Inline` |
| `status` | Actual bounded result name, listed below |
| `callbackEpochMs` | Original native callback time; never replaced by observation time |

Result names are `Success`, `Cached`, `Inline`, `Error`, `Timeout`,
`ServerUnavailable`, `AccessDenied`, `InvalidByteRange`, `InvalidURL`,
`NotFound`, `RedirectFail`, `Cancelled`. `NotFound` is the actual resource
result, not a guessed interpretation of a missing engine or generic error
signal. It does not establish an HTTP status or independently observed UI error.
`Success`/`Cached` establish only source retrieval; submitted code, running
manager, loaded companions and advancing entity effects remain separate facts.

URL observations admit only credential-free `file`, `http`, `https` or `atp`
URLs, up to 4096 characters, without query/fragment or control characters.
Unsupported/private URL metadata makes the source unavailable. Inline callback
strings can contain code: the producer discards that string and exports an
empty URL, never inline source text. No contents, credentials or raw error
messages enter this history. Original URLs are private transport data; public
area output must use the existing owned aliases and privacy rules.

The producer serializes callbacks and snapshots under its own mutex. It never
waits on script execution or retains managers. A regressing native clock,
duplicate/nonincreasing manager generation, duplicate identity, malformed
metadata or a 257th event permanently makes the source unavailable for that
process. Existing total packet bound 262144 UTF-8 bytes still applies; a large
history cannot be silently truncated to fit. There is no history-reset or
history-cleanup command. A real process restart creates a new source instance
and requires a new independently qualified process binding and reader.

The existing `NativeScriptObservation.read(...,require_load_history=True)`
rejects older producers. Once this extension appears, downgrade is rejected
even on later default reads. It validates contiguous sequences, unique event
identities, per-manager increasing generations, original nonregressing event
times no later than native capture, exact status/type relationships and the
whole immutable previous prefix. Final native clock/deadline/process failure
commits neither load history nor other engine/effect state.

`adapters.native_script_loads.result()` selects exactly one original callback
for a complete independently selected URL after frozen sequence/native-time
barriers, optionally under an independently pinned manager identity. Missing,
old, foreign, same-basename and ambiguous events fail. It returns the raw
status, including failures; it never filters for an expected success or invents
`error:'not-found'`. The full Scripts coordinator must correlate this result
with its owned normal input, independently observed current UI/error state and
separate engine/effect/peer observations before publishing the feature result.

The 17 device-free counterexample methods run the real Python reader/selector
and original JavaScript probe with explicitly synthetic native callbacks.
They cover ignored/missing results, original-time preservation, source downgrade,
foreign/barrier/ambiguous matches, malformed histories, rewritten/truncated
prefixes, clock failure, caller mutation, inline privacy and count bounds.
The common quick host inventory registers this module. Full Scripts operations,
restart ownership adoption and independent cleanup joins remain incomplete;
no full feature capability is enabled by this extension.

# Owned missing Script load, version 1

`NormalScriptManager` adds the internal `feature-script-missing` scope, not a
new runner or public capability. It uses the existing normal From URL dialog,
original service-row reader, private owner journal and `NativeScriptObservation`.
The only allowed URL is credential-free HTTP(S), with the exact path
`/feature-fixture/v1/runs/<runId>/tickets/<ticket>/missing.js`; both IDs are 32
lowercase hexadecimal characters. Queries, fragments, escapes, whitespace,
other filenames and borrowed public foundation URLs are rejected before input.
The native E2E input allowlist adds only this missing-resource path; the public
`scripts.*` Python contract and ordinary file-bundle scope retain their grammars.

The scope uses the existing manager journal at schema 4 with
`missingLoadVersion:1` and `missingLoad:null|object`. Existing schema 2 URL/create
and schema 3 file ownership are not migrated or implicitly adopted. Phone now
provides an [explicit observed host-only scope transfer](../adapters/android-phone/SCRIPT_SCOPE_TRANSFER.md)
from a proved stopped file scope, preserving the actual open page. It does not
close/reopen UI to change host schema. Other narrow factories must still
independently retire an existing scope before constructing another. The
separate staged-file owner remains intact until independently verified release.
Never run both manager scopes concurrently or hide an unresolved predecessor.

`load_missing(url, execution)` requires an original typed, guarded, same-PID
execution reader and an owned open manager. It rejects an existing source or
service alias, opens the ordinary dialog and verifies normal field editing.
Immediately before the single Submit it freezes a fresh original native birth,
PID, sequence, capture epoch and complete immutable load-history prefix. It
persists exact source and phase `issued`, plus `loadAttempted:true`, before input.
A lost acknowledgment or missing callback preserves intent. Reconstruction
refuses any second submission, including after a completed failure. Neither a
closed dialog, an input receipt nor absent running rows proves a load result.

`settle_missing(execution)` only reads: original native and load-source identity
must match, the observation must advance past the frozen sequence, and the entire
frozen history must remain an exact prefix. Exactly one actual full-URL callback
must follow both the frozen load cursor and native epoch. A terminal failure is
returned unchanged, including its real status/error category and callback epoch;
only the full feature assertion may interpret `NotFound`. Success, foreign URLs,
ambiguous callbacks, missing results, changed histories and any matching native
engine or independent current service row reject retirement. Failed reads leave
`loadAttempted:true`. Accepted evidence persists the actual completion history
and result before phase `settled`; later reconstruction cannot rewrite that
completion. No stop/restart/load operation is used to manufacture absence.

`close()` retains the normal owned Cancel/tablet/release routes. It cannot erase
an unresolved load. An uncertain submission with a later independently proven
terminal failure may be settled and closed without resubmission. Private journal
writes use the existing compare-and-swap and restrictive permissions. Source
reads retain the original five-second acquisition deadline; ordinary UI waits
retain their existing bounds and the adapter invocation limit remains 60 seconds.
Unknown permissions, process replacement, candidate change or source loss fail.

This component does not prove the visible QML error, owned file/effect/peer
absence, three seconds of quiet cleanup or the complete 19-step Scripts flow.
The complete coordinator still requires all those independent observations.
It must join a real fixture 404, the original `NotFound` callback and a fresh
actual displayed error; ACKs and requested status never substitute for them.
No complete feature triple or physical acceptance is enabled. Native input
instrumentation is source-only and uncompiled. Fourteen host cases simulate
only UI/native callback boundaries; they establish test logic, not a client.

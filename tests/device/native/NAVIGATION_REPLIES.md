# Original current navigation error replies, version 1

This is an E2E-only passive source and strict original-receipt reader. Native
code is uncompiled and device behavior is untested. Host tests execute Python,
the original probe JavaScript and controlled loopback HTTP; native Qt/request
boundaries remain synthetic. No full Navigation capability is registered.

## Actual native source and unchanged behavior

`libraries/networking/src/FeatureNavigationReplies.h` is instantiated only under
OVERTE_E2E_FEATURE_TESTS in the actual AddressManager. Its getter additionally
requires the original GUI thread and --testScript. The existing
`AddressManager::handleAPIError` already checks its actual current RequestScope
and `replyCurrent` before accepting a callback. A passive E2E-only block records
inside that guarded callback. Removing that block leaves the original handler
byte-identical to shared commit e450139746. No request, retry, address, product
setter, cancellation guard or error signal is changed.

Only an actual HTTP(S) reply whose encoded path is exactly
`/api/v1/places/hidden-<run>` qualifies. Unrelated native URLs/errors are ignored.
The actual reply must carry the original typed scoped RequestTicket, match the
AddressManager's current snapshot and remain current. Missing, unscoped or
foreign tickets for an owned-looking callback make this source unavailable.
Native event and snapshot generations come from those actual original tickets;
no generation is supplied in a read command.

The source reads the actual final QNetworkReply URL, HTTP status, native network
error and X-Overte-Fixture-Response header. It never constructs a response ID
from input, status or expected failure. An absent response header remains empty
and cannot establish an owned fixture response. Duplicate/malformed headers are
unavailable. Origins exclude path, query and credentials and remain private.
A bounded weak-QObject identity list prevents recording the same original
callback twice, including after address reuse. No reply property is modified.
The source retains immutable native event IDs, callback clocks and generations.

A record proves a current native error callback only. It does not prove that
the native not-found signal subsequently emitted, the UI constructed its modal,
the user saw it, arrival stayed B or a feature passed. Those require separate
original modal/page/position/image/peer observations from the v15 handoff.

## Closed private transport

Action `feature-navigation-replies` accepts exactly
`{schemaVersion:1,commandId,action,runId}`. All IDs are 32 lowercase hexadecimal
characters; the existing iOS request prefix is `ios-`. There is no URI, expected
state, status, response ID, generation, locator or input operation in a command.
The Test interface preserves original lifecycle/launch and owner-only results
root guards, then obtains the real AddressManager source on its owning thread.
An absent source returns unavailable. The probe writes only the fixed existing
private atomic-file channel `feature-navigation-replies.json` with owner-only
permissions. No public endpoint or permissive writer fallback is introduced.

The native packet has exactly `navigationReplyVersion,commandId,runId,instance,
sequence,processId,capturedEpochMs,currentLookupGeneration,currentLookupActive,
events`. PID, clock, source instance, read cursor and current lookup generation/
activity are native observations. Events are filtered to the requested run and
have exactly `sequence,eventId,runId,responseId,origin,httpStatus,networkError,
contentNotFound,current,lookupGeneration,callbackEpochMs`. The native
contentNotFound flag is computed from QNetworkReply::ContentNotFoundError;
the current Qt ABI's corresponding numeric error is 203. The reader rejects
contradictory fields. Historical events can remain after their context retires;
that does not make them current.

Native limits are 128 immutable events across all owned runs, one billion read/
event sequence values and the JS-safe original generation ceiling. Original
wall/monotonic clock regression or exhaustion makes the source unavailable;
no timer refresh, history truncation, successful empty fallback or reset exists.
A 128-event per-run packet fits the existing 256 KiB observation ceiling.

`adapters/native_navigation_replies.py` sends one fresh read nonce, polls at
most 51 times within five seconds and uses existing PID/clock/result/privacy
validation. Platform callbacks must retain actual installed source, process-start,
foreground/session and private-file guards around every I/O. iOS requires a
separate original native clock acquisition, not host UTC or the packet's own
timestamp reused as its expected freshness. No source path alone attests the
installed code. The reader pins source identity/read clocks/current generation,
retains immutable event prefixes for up to 32 runs and rejects replays, changed
sources, lost guards and late acquisitions.

## Original HTTP and callback join

`owned_missing` additionally requires separately selected original fixture
origin, provider instance/configuration, current run/ticket, input time barrier
and original provider status. These values come from the owned fixture channel;
never obtain an expected origin/identity by copying the native callback under
test. It validates provider status through the existing navigation provider v1
contract and performs a fresh native read.

A match requires the same unpredictable actual response ID in both native reply
and original completed server-write receipt. Both must belong to this run and
current action window; the server receipt must be the current-ticket missing-name
HTTP 404. The native callback must have actual ContentNotFoundError/404, the
separately bound original origin, actual current activity and the same native
lookup generation as the current source snapshot. A newer request or retired
scope cannot lend current authority to an old callback. Missing headers, another
origin/status/ticket, an old action, stale clock, superseded generation or a
server response without native consumption all fail.

The result contains only the original native event and HTTP receipt. It never
returns shared `error:not-found`, modal visibility, current location or a full
feature verdict. The complete adapter must correlate actual modal/source
identity and unchanged B with that original pair, then normally dismiss/recover
and verify UI/storage/settings/input cleanup. This source owns no request or
input lease and exposes no mutation/cleanup operation; immutable callback
history is evidence, not an active resource.

Ten device-free cases cover actual empty versus missing evidence, bounded one-send
unavailable/foreign results, origins/response IDs/native error/current generations,
foreign provider/run/ticket/status/barriers, PID/clock/schema faults, immutable
history across interleaved runs, guard/deadline failures, closed private grammar,
the actual original probe function and an actual loopback HTTP receipt joined
only to its explicit synthetic native boundary. They do not execute the C++ or
qualify any client. Platform component factory registration remains the next step.

The explicit common host selection passed 837 checks with zero failures, errors,
skips or compiler attempts. After passive source review replaced the reply marker
with weak QObject identities, the ten reader/probe/HTTP cases passed again.
Native source remains uncompiled; host tests do not execute either C++ variant.

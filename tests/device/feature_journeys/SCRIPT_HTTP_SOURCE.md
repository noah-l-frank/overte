# Original missing-Script HTTP source, version 1

`ScriptResources` extends the existing controlled feature fixture. It provides
actual HTTP evidence for the normal From URL failure, independently of native
ScriptCache callbacks and the manager's visible Label. It never sets a client
state, runs a script or publishes actor facts. It is currently implemented on
the Android Phone adapter branch; paused platform branches remain unchanged.

The primary fixture automatically provisions this provider only for `scripts`
runs. The ordinary `Client.register('scripts')` first reads authenticated
`GET /script-provider`, requires healthy version 1, zero active Script runs,
zero failed writes/internal errors and an original positive server clock, and
pins the original provider instance. An unavailable provider refuses registration;
failed provisioning rolls back the journal run. One Script run may be active
at once; at most 32 run histories and 256 challenge/response entries per run are
retained. Exhaustion refuses new work; response overflow poisons completeness.

The existing reader-only `POST /runs/<run>/active` still accepts only the closed
normal stimulus. For Scripts it atomically updates the existing journal and
records a unique challenge plus its actual server activation epoch. The provider
receives no desired state, expected HTTP status or assertion. Reused challenges
fail. Authenticated `GET /runs/<run>/scripts` is readable by the reader and the
separate actor role. It requires exactly one fresh 32-hex
`X-Overte-Script-Read` header; missing/duplicate/invalid nonces fail. Public
resource clients cannot read this endpoint, and the actor cannot activate or
retire a run. The secondary browser listener does not expose Script controls.

The status document has exactly `scriptProviderVersion:1`, `instance`, `runId`,
`requestId`, `capturedEpochMs`, `healthy`, `active`, `ticket`, `activations`,
`responses`, `failedResponses`. Original activations contain exactly `sequence`,
`ticket`, `activatedEpochMs`. Responses contain exactly `sequence`, `responseId`,
`ticket`, `status`, `bytes`, `sha256`, `requestAuthority`, `requestScheme`,
`startedEpochMs`, `completedEpochMs`.

Only a real current
`GET /runs/<run>/tickets/<ticket>/missing.js` can create a response entry.
The source intentionally sends the controlled missing-resource JSON. It records
the **actual serialized HTTP status line and response-id header**, the original
body bytes accepted by the socket writer and their actual digest, the original
request Host header, actual TLS/plain socket scheme and original server clocks.
The requested 404 is not copied into the receipt. An actual serialized 200 or
wrong written body remains 200/wrong in the private history and is rejected by
the consumer. No request, missing write observation, short/failed write, bad
clock or incomplete history can create a successful missing-resource receipt.

The connection has a two-second socket bound. The provider holds its source
lock through the original write and commits only after one actual complete
write observation. Challenge changes/retirement cannot overtake that write.
Failed writes and clock regression remain poisoned even if later requests work.
Inactive, old-ticket, foreign-ticket/run and query requests cannot create current
evidence. Raw request authorities and response data remain in the existing
private fixture channel; the ordinary HTTP logger remains disabled.

`Client.script_status()` uses a new unpredictable nonce for every read, checks
the pinned provider/run, strict types/version, original monotonic capture and
immutable activation/response prefixes, and the existing 1500 ms age / 250 ms
future allowance. Its transport keeps the existing five-second bound, response
size cap and redirect refusal. It never retimes an old body or accepts a cached
body with another read nonce.

`missing_receipt(source, run, ticket, fixture_url, after_epoch)` requires exactly
one actual response for the current active challenge, the actual owned origin
(including normalized default port and measured HTTP/TLS scheme), and a response
started after the independent action barrier. It returns the original entry,
not a manufactured `not-found` state. Foreign Host receipts, duplicate requests,
historical tickets and old responses cannot be filtered into one expected proof.
The full coordinator/actor must additionally join the native callback after its
own frozen source barrier, original manager/Label, execution/effect absence and
three-second quiet window. This backend alone establishes no client behavior.

Reader cleanup retires the actual source under the journal lock, waits behind
in-flight writes and removes the ordinary run journal. The client separately
queries the original source and requires inactive ownership. A lost cleanup reply
can repeat this idempotent retirement without replaying client input; an ignored
retirement is detected despite its ACK. Completed original histories remain
private tombstones and cannot resurrect. Retired resource requests return 404
without new receipt entries.

Eighteen device-free cases use the actual existing loopback HTTP server, role
checks, original serialized headers/bytes, nonce replay, foreign origins/tickets,
missing/failed writes, malformed/stale histories, overflow, clock regression,
cleanup faults and lost replies. They prove fixture and test semantics only.
No native client, compiler, install, device or Jenkins run is involved. The [iOS Script coordinator](../ios/SCRIPT_FEATURE.md) separately composes these
originals with client sources and independent role ownership. Provider tests
alone promote no adapter capability or physical acceptance.

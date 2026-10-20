# Owned browser HTTP stimuli v1

`BrowserResources` extends the existing common fixture server. It reuses the
checked `fixture/parity/index.html`, `reference.js`, `client.js`, `injected.js`
and existing verified/ranged video transport. Four original source hashes are
in the existing `resource-pins.v1.json`; missing or changed sources fail before
a response receipt is published. No native browser, product or device ran.

This is a prerequisite packet, not complete Web E2E. Shared journey v10 still
has the [documented draft assumptions](WEB_SOURCE_AUDIT.md). Do not advertise
complete browser capabilities until the breaking journey correction, native
sources/normal inputs, independent publisher and cleanup are composed.

## Lifetime and endpoints

The existing authenticated registration of a `world-web`/`tablet-web` run creates
one new source instance with resource recovery initially unavailable. Only an
already registered challenge ticket can serve assets under the existing exact
`/feature-fixture/v1/runs/<run>/tickets/<ticket>/` path. Other areas do not acquire
browser resource ownership. Closing the original run removes that ownership on
both listeners. Run/ticket/reader/actor material is private and never logged.

The closed document inventory is `index.html`, `reference.html`, `page-b.html`,
`recovery.html`; script inventory is `reference.js`, `client.js`, `injected.js`,
`feature-marker.js`. Original reference controls and script echo remain intact.
Only title, ordinary same-origin links, response metadata and challenge display
are adapted. The marker script only fetches current challenge/PNG; it never
handles bridge messages. Marker freshness does not prove document identity.
Original JS files are byte-for-byte pinned sources, including the deliberate
absence of a cooperative origin filter in the diagnostic client echo script.

`recovery.html` returns an actual HTTP 404 document until explicit restoration,
then HTTP 200. Ordinary 404 documents are not native transport-error receipts.
Every document/script GET has a new random response ID in the actual
`X-Overte-Fixture-Response` header (documents also contain that ID as metadata).
No expected client result or requested identity is supplied by its caller.

Authenticated GET `/runs/<run>/browser` returns exactly
`{browserFixtureVersion:1,instance,ready,sequence,responses}`. Each original HTTP
response inventory row is exactly `{sequence,responseId,capturedEpochMs,ticket,
resource,origin,status,bytes,sha256}`. `origin` is the actual selected listener
(`primary`/`foreign`); timestamp, status, length and SHA describe the bytes served.
Read snapshots are independent copies, never mutable source aliases. Responses
are bounded to 256 per run; inventory exhaustion or clock regression fails closed.

Only the reader role may POST `/runs/<run>/browser/control`, with exactly
`{operation:"restore-resource"}`. Unknown operations/fields, expected status,
publisher/public requests and repeats fail. Persist the full coordinator's input
intent before this once-only control. Lost ACK must trigger status inspection,
not replay. The control changes server availability only: it produces no
document response, navigation, accepted bridge event or client measurement.
Native normal Reload must generate a separately observed successful document.

## Actual second listener

Optional private server config adds `browserPeer:{host,port}`. The CLI owns and
stops both listener lifetimes. The second listener shares the original browser
run/ticket/resource state; it is resource-only even if accidentally given reader
or publisher credentials. Account, run registration, challenges, publisher,
control and private status endpoints are refused there. It serves the actual
original page and echo protocol, rather than a fake page that suppresses input.
Ordinary reference-page foreign URL navigation can target this listener.

The complete adapter must qualify the actual configured two origins against the
native frame/document. A different socket alone does not prove the origin of a
loaded document. A native bridge may legitimately be absent in that document:
the actual normal Send attempt and actual document lifetime must be measured
independently before an unchanged accepted-message count proves rejection.

## Evidence and cleanup handoff

Server responses are HTTP fixture facts only. A matching native main-frame
response ID/status plus original actual DOM/document/frame/URL/lifecycle sources
must establish what a client consumed. A host GET, control ACK, ready flag or
response inventory alone never proves client recovery/rendering/origin safety.
The unchanged actual current 404 document must be observed after server restore,
then a new 200 document only after ordinary Reload. Counters must also reject a
missing/ignored foreign click, fabricated local echo and late old-document reply.

No HTTP `inline.html` exists. Native inline app tests must use the actual data
source API and independently bind original decoded bytes/carrier/context and its
retirement. HTTP documents do not substitute for that route. Back/resume form
behavior still needs source qualification and a breaking closed contract.

The final coordinator must prove original browser/page/script/bridge/keyboard/
media resources retired and both private response/control inventories removed
before closing the run. The new read-only server receipts establish none of
those product cleanup effects. Adapter missing/device untested stays explicit.

Ten device-free cases use actual loopback HTTP listeners to verify original
protocol bytes, repeated 404, actual restore without fabricated navigation,
second-origin roles, forbidden/unknown/replayed controls, unavailable sources,
retired tickets/owners, absent HTTP-inline route, exact ranged media bytes and
bounded immutable receipts. These are fixture/test-logic checks only.

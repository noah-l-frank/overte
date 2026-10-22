# Navigation source contract introduced in v15

Shared test logic exists; all three full Navigation adapters are missing and
untested on devices. This packet adds actual owned HTTP input responses and
source-correct common assertions. It does not run an Overte client, native code,
Qt, a browser or a device. Existing foundation modules remain in the suite.

## Ordinary input and actual state

Bind the original `scripts/system/places/places.js` and `PicoPlaces.qml` sources.
All three platform bases select this normal QML Places page. The native 3D/flat
input resolver must find its actual original controls; arbitrary object names,
private handler calls and requested-state assignments cannot supply input.

State is exactly `location,bookmark,bookmarkName,searchQuery,searchResults,error,
panel,addressDialog`. Every field requires a fresh independent peer observation,
including the actual current page/dialog. A/B are the actual original controlled
viewpoints from `navigation_observation.viewpoint_urls(sceneUrl)` and POSITIONS;
require native arrival plus current grounded position and original rendered
world images. A requested URL, successful setter or network response is not
arrival. Preserve the original process/input continuity checks around each input.

`searchQuery` is the actual original Places `search` field text, not a filter
input echoed by the adapter. `searchResults` projects only original loaded model
rows owned by this run to their directory IDs. Packaged utility rows and unrelated
rows are never copied to public output; preserve their private baseline state.
Actual maturity filtering must include the owned `everyone` entry, using normal
controls only and restoring the original filter during cleanup.

`rebuildPlaces` clears its model, trims/lowercases the actual query and filters
name, description and address. An empty initial query already shows the owned
row. Enter `hidden-<run>` and observe no owned row for three seconds; then enter
`e2e-<run>` and observe the original owned row. The actual field and original
model must both be read. Showing the same preloaded row after ignored typing
cannot pass. An inactive/closed Places page has empty projected query/results;
never read a retired page or infer a live page from cached text.

`open` normally opens Places from the actual Home/app control and waits for the
actual source/page and original directory model. During the first entry, ensure
the owned selected metaverse directory has actually refreshed via its ordinary
UI before accepting the model; READY_FOR_CONTENT can transmit a cached script
portal list and is not itself a network refresh. Later page reopens may use the
same original run's genuine fetched directory response, with a freshly created
page/empty field and current model observation. Respect the original 200ms script
command guard and normal queued UI behavior; never invoke dispatch handlers.

The bookmark recipes use the actual Bookmark current location/add dialog,
normal Save/Cancel, original rename dialog, and normal Delete. Cancelled add or
rename must leave original native bookmark storage unchanged for three seconds.
Add saves actual A (`location.href` in the original script), rename retains the
same stored A address. Independently read actual owned `LocationBookmarks` and
its original backing file revision; an ACK, dialog label or requested address
is insufficient. Keep all unowned bookmarks and preferences intact.

`directory-select` is a bounded composite: normally select the actual original
owned row, observe actual B arrival, then normally close Places. TELEPORT assigns
Window.location and does not promise to close the page. `bookmark-visit` normally
opens Places, selects the persisted renamed bookmark, observes actual A arrival
and normally closes Places. Neither composite invents an automatic close.

`restart-app` must replace the actual process and advance original native launch/
activation counters. Normally dismiss only owned startup navigation surfaces if
present, retaining the exact original bookmark. Never reset its backing file.
The following `open` explicitly creates a current page with empty query; delete
the persisted bookmark there and normally close. Do not inherit a prior page's
search text/model across restart.

## Actual failed named lookup and recovery

`navigate-missing` uses normal Go To, the owned address `hifi://hidden-<run>` and
normal submit. The actual AddressManager must issue its current
`GET /api/v1/places/hidden-<run>` against the selected owned API origin and receive
HTTP 404. A failed serverless scene fetch does not enter this original lookup
failure path. Read original current request identity, URL/name, response status,
lookup failure signal/history and unchanged B arrival/position independently.

The actual `AddressBarDialog::displayAddressNotFoundMessage` creates an
OffscreenUi critical modal with original text `There is no address information
for that user or place`. `error:not-found` requires that current matching modal
and native lookup failure, not a Places inline error or another old request.
After submit the original Go To page may be hidden or remain: observe actual
`addressDialog` either way. `dismiss-error` normally dismisses that matching
modal and closes any still-open owned Go To page. Observe both absent and B
unchanged for three seconds, then recover to A through the original bookmark.
A synthetic popup, foreign-name error or discarded request cannot substitute.

## Owned navigation input provider, version 1

The existing `feature_journeys/server.py` accepts optional private configuration
`navigationProvider:{protocolSignature,sourceRevision,sceneUrl}`. The feature
requires this provider: missing/unhealthy/busy/full readiness or absent provider
on registration fails before normal target actions. Use the exact original
qualified client source revision and original `Window.protocolSignature()` input
(the canonical base64 encoding of its 16-byte protocol hash). Do not derive a
signature from expected success, disable compatibility filtering or change
production protocol behavior. `sceneUrl` is the controlled original scene URL
without a viewpoint/query; A/B are its existing authored viewpoints.

Use the original normal metaverse/server preferences to select this controlled
origin. Bind those original settings and the selected installed build to these
inputs before invoking the full adapter. Preserve/restore the original endpoint,
federation selection, maturity filters and account/profile state. Use existing
TLS trust where the selected client requires HTTPS; never bypass trust or add a
functional endpoint override. The local host tests use private loopback HTTP
only. No production endpoint setter or device configuration is implemented here.

One active owned Navigation run is allowed. Public product-input routes are
exactly GET `/api/v1/places?status=online&per_page=1000` and the single current
owned missing-name route. The directory returns a normal `data.places` array
containing one original input row with owned ID/name, actual controlled B URL,
maturity, tags/managers and matching original domain protocol/capacity fields.
The missing name returns real HTTP 404. Other names/queries, retired runs, missing
active challenges or unrelated routes receive 404 with no owned input receipt.
No account data, public logs or arbitrary caller-specified records are added.

Authenticated GET `/feature-fixture/v1/navigation-provider` supplies readiness
and source input configuration. GET `/runs/<run>/navigation` supplies original
provider instance/run, inputs, current server time, actual active ownership and
ticket, bounded completed response history and failed-write count. Each receipt
has `sequence,responseId,ticket,kind,status,bytes,sha256,completedEpochMs`. Its
response ID is also the actual `X-Overte-Fixture-Response` HTTP header. The digest
and byte count come from actual written body bytes. A response is recorded only
after the bounded socket write returns; this proves server delivery into that
socket, never client receipt, native callback, model load or rendered outcome.

The supplemental `feature-navigation-directory-marker` v1 contract gives each
directory response a fresh normal description value:
`overte-directory-v1:<responseId>`. That value is part of the actual serialized
body and its receipt digest. ID/name/destination remain stable and the provider
v1 envelope is unchanged. Adapters using this stronger source must read the
unique description from the actual materialized model, alongside actual native
body consumption and independent server originals. A freshly timestamped old row
cannot borrow a newer response's marker. Existing consumers still receive the
same ordinary directory schema; the marker is an input, never a UI outcome.

The source holds its original ownership lock across the two-second-bounded
write. Retirement cannot race an in-flight source response. A failed/uncertain
write or clock regression poisons readiness and status validation. Limits are
32 retained run histories, one active run and 256 actual responses per run;
exhaustion is unavailable, never successful empty data. Immutable history is
retained through retirement; it is not an active resource.

The common Journey requires a callable original HTTP source, pins source/run/
input identity, validates immutable prefixes and active current challenge, and
requires at least one genuine owned directory receipt when opening Places.
The missing-name checkpoint additionally requires a newly completed same-ticket
404 receipt after its input barrier. It still separately requires actual native
state, matching modal, current independent peer facts and B position. Old or
foreign response IDs/tickets, missing response history and ACK-only native errors
cannot pass. The ordinary 20-second checkpoint/81-read bound remains unchanged.
Cleanup closes/restores actual owned UI/settings/bookmarks/input and independently
observes the baseline and empty product resources. The existing fixture client
then retires its real provider and reads actual inactive ownership; a successful
DELETE response alone is insufficient. Retain unresolved intent/evidence on any
failure. Device-free checks establish test/fixture logic only, never acceptance.

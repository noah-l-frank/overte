# Graphics subject version 1

`graphics_fixture.scene(run, registered_ticket, actual_fixture_url)` constructs
an isolated serverless entity document using original Overte entity properties:
a Zone with enabled blue distance haze, near/far surfaces, a fine resolution
edge, an actual `mirrorMode:"mirror"` Box, an off-camera colored reflection
subject, and a Web challenge card. Names/UUIDs are deterministic within the
owned run and disjoint across runs. No accounts, preferences, renderer outputs,
expected graphics states or measured verdicts are embedded.

The owner must register the marker ticket in the existing fixture journal
before loading the document. The Web source is the same owned ticket resource
server's `graphics-marker.v1.html`; it polls only the active run's current ticket
and displays the original marker PNG. Requests are uncached. Failure leaves an
old/empty marker, which cannot satisfy current challenge evidence. This card
must be rendered by the actual world renderer; neither its source PNG nor a UI
composite is an acquired world-target result. The page publishes no feature
facts and has no EventBridge input or expected-state API.

Prepare this document only in the isolated owned serverless fixture. Record
original view/location and the complete generated UUID inventory before load.
Use the actual fixture root, never a placeholder URL or arbitrary file path.
The view stimulus is `VIEW`: camera at (0,1.6,0), identity rotation; adapter setup
must establish it through existing ordinary navigation/camera controls and
measure actual alignment. Disable uncontrolled movement and hold actual lighting
and subject/view steady while comparing images. A requested location is not
proof that the scene or camera loaded. Actual current entities, original render
acquisition, pass execution and marker/subject pixels must establish readiness.

Version 4 Graphics begins with actual closed UI and fresh, independently
agreeing original settings/render observations. Fixture setup does not change
preferences. Settings are read/persisted by the owning adapter before ordinary
input; final restoration uses those originals, including non-default values.
Do not confuse Phone's immediate viewport resolution control with Pico's
separate restart-confirmed runtime-eye resolution. Actual Haze/Mirror pass
measurements are separate from the settings source. Unsupported rendering or
missing Web/reflector/haze cannot be replaced with synthesized pixels or flags.

Cleanup must remove/observe absence of every owned UUID, cancel its Web resource
activity, restore original settings/view/location and verify that no unowned
entity changed. Do not delete an existing world's entities or adopt a colliding
UUID. Failed/partial preparation retains intent and blocks a green result.
The generator is registered with four device-free construction/counterexample
checks. They prove stimulus shape and isolation only. Native acquisition, actual
geometry visibility and all product/device rendering remain unqualified. This
fixture is an adapter prerequisite; it does not activate `feature.graphics.*`.

## Controlled HTTP scene resource, version 1

The existing fixture server now accepts an optional private configuration field
`"graphicsProvider":{"fixtureUrl":"https://<actual-origin>/feature-fixture/v1"}`.
The URL must be canonical, credential-free and match the real request scheme and
Host exactly. No placeholder/forwarded/request-selected origin is used. The
normal server lifecycle owns the provider; no additional test service is needed.

`GET /graphics-provider` and `GET /runs/<run>/graphics` are private reader/actor
routes. The latter requires exactly one fresh `X-Overte-Graphics-Read: <32hex>`
nonce. Status version 1 identifies the provider birth, actual fixture URL, run,
request nonce, original capture epoch, health, active ownership, current ticket,
immutable scene ticket and complete bounded activation/HTTP response histories.
`Client.graphics_status()` pins these identities and verifies append-only
histories, clocks, original scene byte digest and request scope. An actor cannot
activate or delete a run. Calling it does not set any product state.

The first registered Graphics challenge becomes the immutable `sceneTicket`.
`/runs/<run>/tickets/<sceneTicket>/graphics-scene.v1.json` supplies the original
generated entity document with the actual owned marker URL. It remains byte
stable across later challenges and ordinary app restarts; its marker page polls
the independently current ticket. Another ticket cannot select a replacement
scene. A missing provider, foreign run, changed origin or retired owner cannot
serve a successful scene. Generic host simulations may still register Graphics
without this optional provider; a complete product adapter must require it and
must fail when it is absent.

Each original HTTP response receipt records a unique response ID, serialized
status, original byte length/SHA-256, scene and active tickets, request authority/
scheme and start/completion epochs. The real socket write must be observed once
and complete; ignored, truncated, changed or duplicate writes poison readiness
and publish no receipt. Recorded non-200 status stays non-200. These are resource
delivery facts only: they cannot prove that a client requested, loaded or rendered
the subject. Actual native entity/view and same-frame image checks remain required.

Retirement holds the same ownership lock as in-flight scene delivery, preserves
original histories and prevents later scene replies. An independently read
retired status is required after the reader's delete ACK when this provider has
been attached. Native Web cancellation, entity absence, preference/view restoration
and host journal retirement remain separate required cleanup. Provider bounds
are 32 retained runs, one active Graphics run and 256 activations/responses per
run. Exhaustion retains provenance and fails closed. All routes retain the
existing authorization, no-store headers, private logging and two-second socket
budget; these are host-only fixture changes, not device acceptance.

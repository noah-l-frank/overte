# Opt-in navigation scene and visible challenge input

The shared `NavigationResources` provider can explicitly opt into
`scene_profile="navigation-marker-scene-v1"`. The private fixture CLI accepts the
same opt-in as `navigationProvider.sceneProfile`; its existing three original
input fields remain unchanged. Default version-1 directory/named-404 consumers
retain their original envelope and behavior. No complete iOS capability is
advertised by this addition.

Use an actual owned origin and a distinct scene path, for example
`http://<owned-fixture>/navigation/scene.json`. An existing original world can
then be restored separately by the future whole-operation owner. Normal Go To
loads the scene; no entity/pose/camera setter is added to the adapter. The scene
route matches the configured host, effective port, scheme and path, accepts only
empty or the three existing bounded viewpoint queries, and cannot shadow the
API or generic feature resource routes. Unknown/foreign/disabled requests fail.

The version-1 scene stimulus retains the original five controlled navigation
boxes and root viewpoint. It excludes the unrelated interactable/entity script
and adds one collisionless Web marker with a stable run-scoped UUIDv5, identity
rotation, position `(1, 1.3, 0.8)` and dimensions `(2.2, 0.55, 0.01)`. Its source
is the same origin's registered-run/ticket `navigation-marker.v1.html` resource.
These values describe controlled input, never observed scene/render effects.

The marker page follows the existing Graphics marker mechanism: it fetches the
actual generic run `/current` endpoint without caching, then points its image
at that ticket's original `marker.png`. The document polls every 100 ms with at
most one current read outstanding. No wanted location/state, renderer receipt,
adapter acknowledgment or outcome is sent to the page. The existing Graphics
HTML bytes remain unchanged for its original resource name. The Navigation page
uses a block image and hides overflow so browser inline-image baselines cannot
introduce scrollbars into its card geometry.

`/feature-fixture/v1/runs/<run>/navigation-scene` is an authenticated read of the
new independent version-1 scene source. `Client.navigation_scene_status` retains
and validates its original immutable history separately from the unchanged v1
directory/missing-name history. Each successful scene socket write records its
original response ID, active ticket, exact body byte count/hash and completion
time under the original provider source instance. Failed writes poison the
source; they do not become successful empty histories. The same provider lock
spans the actual bounded write and retirement, so retirement cannot overtake an
owned write. Clocks and earlier receipts remain unchanged on repeated reads.

After retirement the run-scoped marker scene and registered HTML/PNG resources fail closed. The
existing retired generic journal boundary returns HTTP 400 for `/current` and
registered HTML/PNG lookups; it does not return a new successful challenge. This establishes only fixture input retirement.
Actual native Web document/texture/callback drainage and process quiet must be
observed separately before retiring whole-operation responsibility.

Host verification exercises actual local HTTP scene/HTML/PNG routes, the actual
marker JavaScript against loopback `/current` and PNG responses with a modeled
DOM, original byte receipts, changed tickets, source history, socket-write
ownership and repeated retirement. It does not establish actual Web rendering,
native source identity, pixels or iOS acceptance.

The passive [native state version 2](NAVIGATION_STATE.md) now observes the actual
run marker, and the [challenge-image component](NAVIGATION_CHALLENGE.md) decodes
its visible current ticket using original GPU geometry. The durable Worlds owner
and independent publisher still need to acquire, retain and join these sources
through the complete ordinary flow, restart, failure recovery and cleanup.

## Static original base input

The same explicit marker-scene profile now also supplies a static original
resource. For `/navigation/scene.json`, its URL is `/navigation/base/scene.json`;
other configured paths use the same deterministic base subdirectory. Both
resources retain the existing normal-navigation `scene.json` filename. The host,
scheme and effective port stay fixed. Legacy directory-only providers enable
neither this route nor its source endpoint.

This input contains the unchanged five original navigation boxes and root
viewpoint, with no interactable/entity script, run marker, Web entity or ticket.
The provider freezes its exact JSON bytes at construction. They remain identical
before registration, during a run and after run retirement, so a separately
prepared original test scene can be reloaded without restoring a retired marker.
The static resource belongs to the fixture lifetime, separately from an active
run's dynamic resources. Serving it after retirement does not resurrect a run.

`GET /feature-fixture/v1/navigation-base-scene` is an authenticated input-only
source, readable by the existing adapter-only credential. Its version-1 packet
retains the original provider instance, source revision, static URL, exact byte
count/hash, original server capture time, availability/completeness and immutable
actual socket-write receipts. Receipts have no run or ticket. The provider lock
spans the actual bounded socket write, so a snapshot cannot report a completed
receipt while that write is blocked. Failed writes poison availability instead
of returning a successful empty history. The retained receipt budget is bounded.

Source bytes and HTTP receipts establish controlled input only. Initial scene
admission must independently match the actual native
[commit body and editable map](SCENE_INVENTORY.md), preserve original current
pose/view/preferences/panels and reject unsaved edits before ordinary Go To.
Restoration must independently observe the same actual native committed body
and editable map, grounded pose and lifetime/quiet conditions. The static route
does not prepare an app, change its startup URL, repair a product or establish
any of these native effects. Whole scene ownership remains to be integrated.

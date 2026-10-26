# Canonical iOS Assets transport and read ownership

`IOSAssetsRuntime` connects the existing file, picker and independent server
reply owners to the canonical candidate, installed-source, PID and existing SDK
session gates. It creates no session, launches no app and advertises no Assets
capability. The existing explicit native `normalScripts` input profile remains
a source-factory prerequisite; no Script or alternate input manager is loaded.

The factory uses the existing `FeatureObservation` command/HTTP/private AFC
channel and an independently nonce-bound native clock reader. A final guard
checks the same candidate/process, source lock and original outer Assets budget
immediately before each native HTTP request. Normal input retains its existing
channel and requires the same final checks. A callback returning `False` cannot
silently permit delivery. File and reply source factories reject a foreign PID
or a non-iOS clock source.

The fixture accepts only the two closed Assets command grammars. Input bundle
carriers use the existing 128 KiB ceiling; reply commands have an 8 KiB ceiling.
The normal 4 KiB gate remains in force for other actions. These are transport
ceilings, not new valid file sizes: original per-file, aggregate, field and
ownership validators still run. Unknown fields, foreign paths, malformed
commands and oversized bodies cannot replace the fixture's current command.

The private runtime methods are:

- `_assets_sources(selector, lock)` obtains the guarded original transports.
- `_assets_components(selector, run, role, fixture_url, lock)` opens the run/role
  file, picker and reply ownership stores under the same held source lock.
- `_assets_readback(...)` obtains actual independently read server bytes through
  the existing GetAll/GetMapping/GetInfo/GetAsset owner, then retires read leases.
  Its result establishes neither ordinary upload nor bake/import success.

A failed or uncertain readback attempts observe/retirement through the exact
durable read owner. It never repeats a start or cancellation. Secondary cleanup
failure is retained privately on `runtime.cleanup_errors`; the original primary
exception object is raised unchanged. Neither exception supplies feature facts.
The original unresolved job and issued cancellation stay in the ownership WAL,
so reconstructing cleanup can observe actual weak drainage without resending.
Budget, candidate or source loss may prevent cleanup; failure cannot erase that
responsibility or become successful absence.

The host entry points are
`ios.self_tests.test_ios_assets_runtime.AssetsRuntimeTests` (ten cases) and
`ios.self_tests.test_ios_assets_fixture_transport.AssetsFixtureTransportTests`
(four cases). Root-coordinated run 260 passed all fourteen and the fifteen
existing reply cases; the combined selection passed 69 cases in 24.144 seconds.
It exercises actual Python candidate/runtime gates, private ownership files,
HTTP/AFC codecs and an owned loopback fixture. Native/Qt/AssetClient sources,
installed-bundle/preflight boundaries and producer clocks are explicit models.
It establishes no compiler, installed device, AssetServer, physical deadline,
model consumer or oven qualification.

Whole Assets remains partial. The next vertical must connect ordinary bundle
selection, review/primary choice and the destination confirmation to original
upload callback/lifetime observations and independent server readback. Current
helpers do not provide shared scenario dispatch, Actor publication, baking,
world import/rendering or full server/client cleanup qualification.

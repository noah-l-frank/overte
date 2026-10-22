# Separate Snapshot Photos original reader

This standalone, opt-in iOS test application reads the actual original resource
of one explicitly selected Photos asset. It is never included in the Overte
product build. The product's existing Photos AddOnly declarations are unchanged.
The companion alone declares ReadWrite usage. Its normal **Authorize Photos
read** button invokes the actual OS authorization flow. Companion authorization
does not establish the Overte client's Save authorization.

The input fields accept only the run identifier, actual native Save placeholder
identifier, observed controlled capture filename and fresh inspection nonce.
There is no expected hash, expected byte count, expected image or success input.
The **Read Photos original** button first persists its responsibility in an
exclusive run directory. It then fetches the actual asset and requires exactly
one original photo resource with the same actual filename. The PhotoKit resource
manager streams its unchanged bytes into a private, exclusively created file.
Networking is disabled; a missing or unavailable original fails.

The app retains the read responsibility after errors. It never issues the same
read again after another tap, a lost return or a process restart. An existing
run directory cannot be overwritten or adopted as a new acquisition. A failed
or partially written record remains diagnostic evidence. Callback histories are
bounded and overflow fails the source rather than dropping old callbacks.

`OVTPhotosRead` is held by the initiating stack and actual PhotoKit callbacks.
The journal observes it weakly. Callback exit and actual object deallocation
are separate events; terminal API completion alone does not prove drainage.
An ordinary **Inspect original owner** button records the actual weak state,
ReadWrite authorization and a new native UTC/monotonic clock. Reusing an
inspection nonce is refused. This source never imports the Overte process's
monotonic clock or relabels host/AFC file times as native observation times.

The separate **Delete this owned Photos asset** button requires the completed
original read, actual weak expiry and full ReadWrite authorization. It verifies
the same actual asset still has exactly the original controlled photo resource,
then durably records one deletion intent before the real PhotoKit transaction.
Any OS deletion confirmation remains an actual system input. Both transaction
blocks and their actual weak owner remain independently observed. A later fresh
inspection performs a new asset lookup under unchanged full authorization.
Limited-library invisibility cannot establish deletion. Neither an ignored
deletion, completion ACK, retained callback nor an old absence passes the host
retirement join. One absence still requires the outer quiet window.

The app's Documents directory contains:

- `snapshot-photos-<run>/photos-original.json`: version-1 native original ledger.
- `snapshot-photos-<run>/original.bytes`: the unmodified resource stream.

Metadata uses private atomic replacement with file and directory synchronization.
The bytes file is exclusive and synchronized before completion. A later native
query is valid only after the last retained event; it cannot make a late
callback current using an earlier query. The host reader separately verifies
the exact original bytes against the native SHA-256 and actual client's Photos
transaction/placeholder. No image conversion or image-cache API supplies bytes.

The source follows Apple's [original asset-resource data API](https://developer.apple.com/documentation/photos/phassetresourcemanager/requestdata%28for%3Aoptions%3Adatareceivedhandler%3Acompletionhandler%3A%29?language=objc).
The separate [normal export control](../SNAPSHOT_EXPORT_CONTROLS.md) and
[native export](../SNAPSHOT_EXPORTS.md) sources provide the client side.

## Qualification and next integration

Eight no-build host tests use real private original files and actual native-export
codecs over modeled PhotoKit/companion observations. They reject wrong assets,
foreign runs, changed bytes, missing resource selection, stale/reused queries,
changed PID/source birth, late/unreturned callbacks, missing completion and
rewritten historical prefixes. Actual commit/weak expiry/full-access absence
joins also reject ignored/failed deletion, limited visibility and reused read
ownership. These tests do not execute this Objective-C source.

The standalone CMake entry requires explicit `CMAKE_SYSTEM_NAME=iOS`,
`OVERTE_E2E_FEATURE_TESTS` and a separate
`OVT_SNAPSHOT_COMPANION_BUNDLE_ID`. It does not select signing credentials,
install an app, alter the client or start any laboratory. CMake configuration,
native compilation and device execution have deliberately not been performed.

Whole Snapshot integration still needs explicit installed-code admission for
the companion, ordinary candidate-bound UIKit input and original AFC transfer,
the normal owned-asset deletion route and its quiet window, a separate Share recipient,
the client's OS permission recovery and paired cleanup. The Photos result
retains `cleanupRequired: true`; it cannot advertise a complete feature or
release ownership. An actual Share recipient cannot be substituted with this
Photos resource reader.

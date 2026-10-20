# iOS original navigation error replies

`FeatureObservation.navigation_replies()` validates the closed iOS-prefixed
read command and uses the original private HTTP/AFC transport. It reads only
`feature-navigation-replies.json` under the qualified owned results directory,
with a 256 KiB ceiling, fresh nonce, original PID and separate native clock
acquisition. Host UTC and the packet's own timestamp cannot stand in for that
independent clock. It sends no expected state or URI to the native getter.

`IOSNativeMixin._navigation_replies` uses `_native_source_scope`: the original
session/fingerprint/generation and native process are checked around each I/O,
without opening or requiring a Scripts editor/profile. The canonical physical
adapter checks its actual installed-code/candidate lease before entering that
scope and preserves the installed binding in its process-continuity closure.
The unbound legacy factory explicitly refuses both entry points. Cleanup-only
missing-candidate access fails before target lookup or I/O. No default process,
installed identity or empty native history is invented.

Follow the [passive source and original HTTP receipt join](../native/NAVIGATION_REPLIES.md).
The exact actual response ID, origin, current native RequestTicket generation/
activity, run, ticket, native error and action barrier must agree. The result is
raw original callback/HTTP evidence; actual modal identity, grounded B position,
Places/model/bookmark/UI inputs and complete independent observer/recovery/
cleanup joins remain missing. No complete Navigation triple is advertised.

All 386 explicitly selected iOS host checks pass without failures/errors/skips
or compiler attempts. Five new HTTP/AFC/clock/session cases exercise the actual
reader/factory, scope changes, missing/foreign sources, retired lookup, foreground
loss and unbound refusal. An additional case exercises the actual canonical
installed adapter with synthetic native/OS/artifact sources: replacing its
original artifact blocks the retained reader before another native command.
Native code remains uncompiled; no device, SDK service, installation or build
ran. The process plugin remains uninstalled/inactive, published candidate inputs
remain unavailable locally and the existing cold-preflight/timeout gap is not
relaxed. None of these host results supplies physical acceptance.

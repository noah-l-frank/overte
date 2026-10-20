# Read-only iOS process source v1

This Appium plugin implements the previously assumed `mobile: overteProcessInfo`
command without a cached foreground PID or a fabricated background process.
It is source-only: nothing was installed, activated or started. Hardware and
the Proxmox laboratory remain untested. Preparing/activating a qualified plugin
in the Proxmox runtime is a later deployment action, outside this local task.

## Qualified API and scope

The code targets the existing locked Appium 3.7.0, XCUITest 12.8.0 and RemoteXPC
5.15.3 API. Production entry loads and checks the actual peer package versions;
wrong/missing versions fail. Local read-only SDK sources were inspected as API
references, not as evidence of the live Proxmox installation:

- XCUITest `mobileQueryAppState(bundleId)` reads WDA `/wda/apps/state`.
- The driver's `remoteXPCFacade.requireService` receives the original
  `Services.startDVTService` factory and session-bound configured device.
- Actual DVT `processControl.getPidForBundleIdentifier` returns the selected
  bundle's PID, or numeric zero for absence, including while it is backgrounded.
- Original `DVTSecureSocketProxyService.close()` clears its connection/socket,
  retires its handshake and destroys the original Node socket.

The plugin accepts only a real iOS driver, current original session, configured
device and exact configured bundle. Requests cannot select another app/device,
an expected PID, arbitrary service, operation, signal or filesystem path. It
performs no launches, installs, kills, signals or changes to product behavior.

## Wire contract and original observations

Both commands accept exactly one argument object, exactly `{bundleId}`:

`mobile: overteProcessSourceInfo` returns `{processSourceVersion:1,source:
"dvt-bundle-pid-xcuitest-state",instance,available,cleanupPending,sdk}`. Instance
belongs to the actual observer/driver session, not the app. SDK contains the
actual verified peer versions; available does not attest a running app or code.

`mobile: overteProcessInfo` returns null only after actual OS/DVT absence agrees,
or exactly `{bundleId,pid,foreground}`. The bundle is the query scope used in
the original DVT lookup; PID is the actual reply and foreground is actual WDA
application state. This mapping is separately correlated with the actual native
CoreFoundation bundle ID/PID during byte association. It is not an expected
identity echo. No device selector, path or raw exception is exported.

Each read independently acquires actual OS state, actual PID, actual OS state
again and a second actual PID. PID must remain equal; states must remain in
the same foreground/background/absence class. States 2/3 mean a real background
process, state 4 foreground; 0/1 with DVT PID zero mean not running. Contradictory
states, noninteger/foreign/changing PIDs and scope/session replacement fail.
No `activeAppInfo` fallback can accidentally identify SpringBoard as Overte.

The five-second monotonic deadline includes actual source closure. One original
DVT lease/socket is retained before validating late acquisition. Success requires
that original socket destroyed and the original service connection/socket gone
and handshake retired. A close ACK alone fails. Timeout destroys only an owned
socket, retains uncertain/pending acquisition and prevents subsequent successful
reads in that driver. Late acquisition still runs its owned close path; its
result never becomes output. Concurrent reads are rejected, not silently merged.
The eventual full coordinator must serialize its primary/independent source
transactions, as with the existing single-slot native command transport.

Plugin `deleteSession` always delegates original teardown, then refuses successful
cleanup while an original lease/acquisition remains unresolved. Controlled errors
are `OVT_IOS_PROCESS_SOURCE_UNAVAILABLE` or
`OVT_IOS_PROCESS_SOURCE_CLEANUP_INCOMPLETE`. Original SDK diagnostics remain
private laboratory logs; the adapter's existing closed error boundary must
continue discarding raw server exceptions.

## Handoff and verification

The package declares the exact existing SDK peer dependencies; it has no build
or installation scripts. A future qualified Proxmox runtime must package/hash
these original plugin files with its existing immutable source/runtime closure,
register `overte-process-source` and expose the metadata command before bound
mode can use it. This packet does not modify global workflows, runtime guards,
the installed workstation copies or any live Appium extension registry. Missing
plugin/source support must remain a hard binding failure, never an unbound
fallback. Full canonical bundle/process association remains the next packet.

Nine host cases execute the original observer and plugin entry against synthetic
SDK responses and original unconnected Node Socket objects. They cover fresh
foreground/background/absence, PID/source/scope changes, leaked close ACKs,
late/stalled acquisitions, another socket left untouched, unknown ownership,
concurrent reads, closed dispatch, unchanged other commands and SDK mismatch.
These validate source/test logic, not an actual DVT connection or a device.
The additional read-only module-load check passes against the existing locked
local SDK reference without constructing a driver/server. Metadata uses Node's
original package search order and actual driver dependency context, including
ESM-only packages that do not export a CommonJS entry or package.json. The host
counterexample covers that exact layout and rejects a neighboring foreign SDK.

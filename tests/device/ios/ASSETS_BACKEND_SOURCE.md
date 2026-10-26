# Passive Assets backend originals and owned collector

Feature 13 remains closed and the source-complete area count remains 5/14.
The backend hooks saved in `e9f47a0fb7` remain uncompiled. Host validation now
connects their closed protocol to an owned process reader, immutable collector
journal, separate passive domain credential and exact original-byte exports.
No native server, oven, compiler, device, laboratory or service was started.

## Independent process and source ownership

`LinuxAssetsBackendProcess` reads the actual Linux PID start identity, boot UUID,
role-3 command line, fixture owner token, XDG config home and source environment.
It pins the actual executable FD/stat/SHA and the original private source/config
directory inodes. Every guard rechecks them; PID reuse, executable replacement,
alternate roles, inherited foreign source paths and replaced directories fail.
The raw process-owner token is never exported, recorded or printed.

The existing default-off native feature macro plus Linux and
`OVERTE_E2E_ASSETS_SOURCE_ROOT` gate the original source. This change enables no
build option and starts no process. The native admission binds actual server and
domain UUIDs, owner SHA, PID and source/data-root inodes. Missing hooks, missing
admission, malformed/incomplete facts or uncertain originals remain unavailable;
they never become qualified empty maps, files or workers.

## Immutable intent and exact original exports

`AssetsBackendFiles` owns a separate private journal directory. Each exclusive,
fsynced record carries the previous record's SHA; the directory is also fsynced.
The original admission and every prior acquired query/original/saved file are
reread with original stat, bytes, SHA, private mode, UID and link checks. Every
directory census uses a fresh open-file description of the pinned directory,
so a retained enumeration offset cannot turn real membership into an empty set.

The collector durably saves intent before publishing a closed passive query.
The native source cannot receive expected mappings, paths, hashes or desired
outcomes. It exclusively writes a query intent, then one original observation,
then its saved marker. The collector checks the native original's actual inode
against that marker. Missing markers retain responsibility; a same-byte inode
replacement cannot be adopted. Unknown publication is observed after restart,
never retried or silently retired. Original IPC and the host journal remain
retained; host detachment releases only this reader's descriptors.

Exports contain actual base64 bytes and stat/SHA references for admission,
native query intent, native observation and saved marker. Their recorded host
read bracket remains historical when exported again. Backend epoch/monotonic
clocks stay in the AssetServer process domain; no backend stamp is relabeled a
device stamp or compared as though it shared the device's monotonic clock.
Queries within one run may use successive tickets; each original joins its
exact ticket. Original source event/clock prefixes must still advance.

## Narrow opt-in domain route

`fixture/domain.py --feature-assets-backend` provisions separate private source
and journal directories per actual stack generation. Only the role-3 child
receives the source-root environment. This is a default-off source path, not a
new product setting. The private ready file contains an `assetsBackendReader`
configuration with one separately scoped token and actual kernel binding.
That configuration is excluded from stdout. Existing fixture/domain-control,
adapter-reader and independent actor credentials retain their original scope.

The exact `/v1/assets-backend` route accepts only Observe/Poll/Original for an
owned query nonce/run/ticket, through `X-Overte-Assets-Reader`. It cannot change
permissions, mappings, worker behavior, fixture state or peer facts. Request
bodies are bounded to 1024 bytes with duplicate/header/transfer guards; source
exports are bounded to 4 MiB. Retried Observe can only inspect the already
journaled native nonce. It never publishes that nonce again. A second run or
foreign query/ticket is not adopted into the existing collector.

`AssetsBackendClient` accepts only that loopback route and narrow configuration,
requires the caller's durable pre-transport intent and current process/native
guard, refuses redirects and validates all four exported originals. It receives
no general domain-control token. Original reads preserve historical brackets
and do not move its observation cursor. The ordinary iOS primary command server
and probe have no invented backend command or handler.

## Worker and filesystem facts; remaining integration

The native draft reads actual mappings/map bytes, bounded blobs and hidden meta,
permissions, queued/pool counts and real task run/callback/weak-holder lifetimes.
It does not hold tasks alive or use sticky `isBaking` as completion. Run/callback
return and lease/shared-owner/QObject expiry remain independently required.
The source and parser retain oversized bodies as unknown rather than inventing
readability or bake output. Native callback/Qt/FS behavior is still uncompiled.

This packet supplies original transport. The later owner described in
`ASSETS_BACKEND_RESTORATION.md` now joins the ordinary mapping/upload successor
to fresh backend observations, exact baseline/foreign/hidden/blob preservation
and native-plus-host quiet. Historical sessions without that complete same
successor still retain `server-retirement`; old picker phases stay literal.
Normal baking/Add-to-World, actual model consumers, whole dispatch and complete
paired cleanup remain open. Native task permissions and full capability did not
change.

## Exact host validation

- Original source/work selection: 12/12 passed in 0.032 s, log
  `.ios-host-tmp/assets-backend-source-first-20261026.log`.
- Collector/kernel boundary selection: 23/23 passed in 0.539 s, log
  `.ios-host-tmp/assets-backend-collector-second-20261026.log`.
  The first run exposed the retained directory enumeration offset; the fixed
  implementation opens a fresh directory description without weakening census.
- Closed domain handler/client/collector composition plus those regressions:
  32/32 passed in 0.860 s, log
  `.ios-host-tmp/assets-backend-control-second-20261026.log`.
  The first route run passed 31/32 until the HTTP boundary model supplied the
  real urllib handler's normal Content-Length serialization.

The tests execute actual Python codecs, tempfile/stat/SHA, weak references,
journal/fsync and original HTTP-handler bodies. `/proc` contents, HTTP transport,
native task/clock/Qt/server/oven boundaries are explicit host models. They start
no socket, thread, child or service and do not qualify any native execution.

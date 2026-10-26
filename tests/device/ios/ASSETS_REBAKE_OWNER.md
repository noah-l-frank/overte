# Ordinary Assets rebake joined to backend originals

`OwnedAssetsBaking` joins one WAL-owned normal checkbox input to the independent
backend collector's retained originals. It binds the same actual source
carrier, page, file token, run/role/session, process and reader configuration as
the normal Usage owner. A private closed runtime factory constructs these
owners without advertising a capability or launching a process/service.

The new `asset_backend_rebake.ready` predicate is separate from the unchanged
first-upload `bake_ready` rule. Rebaking admits an existing same-hash mapping
only when both baseline work snapshots are actually drained. It retains the
original source blob's exact body/identity and requires exactly one new Bake
task for that path/hash after the baseline, the original successful callback
and run returns, expired lease/shared/QObject owners, no pending bodies/queues/
pools, current successful bake-version metadata, and a readable actual output
blob distinct from the source. Previously baked bytes or status alone cannot
qualify another bake. Multiple new tasks remain ambiguous even when all return.

The UI intent exists before delivery. An uncertain return is recovered only by
the normal owner's original frames and subsequent read-only backend samples;
the checkbox mutation is never resent. A lost parent save preserves the
original input error and the independently durable UI journal. Completed
samples remain immutable; observing later native completion uses a new owned
read query, while an incomplete query is only polled under its original nonce.
An initially busy baseline similarly retains its original and can become
admissible only through a bounded new read before any checkbox is delivered.

Proof reuse reopens the exact private source originals and rejects changed
input-frame inodes or parent/child WALs. Historical ownership replay performs
no transport or clock query. Qualified rebaking does not retire server data,
UI clients or imported entities. Incomplete baking stays blocking unless the
actual client and independently proven backend restoration have both finished.
The separate possible-model retirement requirement remains unchanged.

## Verification and remaining scope

Eight `AssetsBakingOwnerTests`, eight `BackendRebakeTests`, nine unchanged
`BackendEvidenceTests` and ten `AssetsRuntimeTests` passed: 35/35 in 42.553
seconds. Private log:
`.ios-host-tmp/assets-baking-owner-final-baselines-20261026.log`.

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=.:tests/device:tests/device/self_tests:tests/device/ios/self_tests \
TMPDIR="$PWD/.ios-host-tmp" timeout 120s python3 -m unittest \
  test_ios_assets_baking_owner.AssetsBakingOwnerTests \
  test_asset_backend_rebake.BackendRebakeTests \
  test_asset_backend_evidence.BackendEvidenceTests \
  test_ios_assets_runtime.AssetsRuntimeTests -v
```

The event-driven fixture executes the original QML checkbox handler over an
explicit existing-server FBX input. Independent backend journals, blob files,
hashes/inodes, weak host holders and export bytes are real. Native process,
Qt/server/oven boundaries are explicitly modeled. In particular, the fixture's
output begins with `Explicit modeled oven output`; those bytes are not evidence
that an actual oven compiled or ran. Tests assert source phase `ready` and zero
uploads for this focused existing-asset case.

Counterexamples cover ignored/lost input, lost parent CAS, exact source inode
replacement, pending callback/run bodies despite settled UI/output, live weak
owners, nonquiet baselines, duplicate new tasks, original input recreation,
missing outputs, failed/stale metadata and a real pending-to-drained baseline.
Successful pure inspection retains
server and client responsibility without issuing another query. Earlier
selections passed 17 cases in 5.539 seconds and 21 in 22.987 seconds, then 34 in
36.772 seconds before the bounded successive-baseline recovery addition.

No native build, compiler, device, real server/oven/service or remote write ran.
This establishes neither an ordinary complete FBX upload nor loaded/rendered
models, resource consumption, peer publication or paired final cleanup. Those
remain the next integration dependencies. Full Assets capability is closed;
source completion remains 5/14.

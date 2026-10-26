# Ordinary baked FBX namespace cleanup

The private `OwnedAssetsBakedTree` profile uses the existing Tree1 ordinary
Browse/Rename/Delete recipes. Tree1's literal envelope, exact namespace-only
delta and defaults are unchanged. The new closed envelope binds its own canonical
`baked-tree` WAL to the actual adopted Model UUID, original parsed source/backend
indices, original input hash, qualified output path/hash and meta hash.

The extra mapping delta is necessary because
`AssetServer::deleteMappings()` removes an unused original blob, then calls
`removeBakedPathsForDeletedAsset()` recursively for that blob's own
`/.baked/<inputHash>/` prefix. The adapter never invokes that method or an asset
mutation service itself. It drives the existing rendered normal buttons.

Before this profile can reserve, the original independent pre-upload backend
baseline must contain neither that input hash as a mapping/blob nor its hidden
prefix. The already qualified parsed-input/backend sample must contain the
exact hidden output and meta mappings. The independent binary mapping inventory
before Delete must agree with every qualified hidden mapping and preserve all
other rows. After Delete it may lose exactly the renamed owned namespace and
those qualified hidden paths. Existing baseline output/meta blobs, foreign
same-hash aliases, foreign row changes and unrelated hidden paths are rejected.
The exclusive before-state is checked before ordinary Delete confirmation,
then the independent after-state must match its exact permitted delta.

The fresh private upload/parser composition applies the same conservative
original baseline check before the first upload can trigger implicit baking.
This rejects already shared content before mutation. It is **not a global actor
lock or fresh permission/alias admission at each later command**: an actor race
since that baseline still needs a separate original, input-bound admission and
remains an open full-journey requirement. The profile deliberately supports only
the pinned fresh `asset-stand.fbx` route.

The parent backend owner must independently observe exact original mapping,
blob and meta restoration, returned/drained worker bodies and the unchanged
three-second native/host quiet interval after actual client retirement. Tree
deletion alone establishes none of that. Local Model deletion also remains a
separate ordinary Create child, with the actual cached QObject/HFM kept alive
and owned when its original shared lease expires. No actor, renderer, texture,
decoder, GPU, process or whole resource retirement is inferred.

## Current qualification boundary

Eight pure predicate cases passed in 0.052 seconds. They cover exact qualified
delta, foreign row changes, same-hash aliases, prior baseline blobs, duplicate
rows, missing output/meta and unavailable/incomplete original work. Log:
`.ios-host-tmp/assets-baked-tree-facts-20261026.log`.

The existing-foreign-hash connected negative passed in 1.203 seconds, with no
upload, implicit bake or normal baking input. Log:
`.ios-host-tmp/assets-baked-tree-shared-hash-20261026.log`.

The first new fresh upload→implicit bake→ordinary OFF/ON→parsed Model→namespace
Rename/Delete→ordinary Model Delete→normal Home/client closure→independent
backend restoration attempt reached its unchanged outer360s limit (exit124).
No assertion/guard traceback occurred. Retained owner WALs recorded baked tree
`deleted`, Model removal `model-gone` with exactly one original observation and
no context closure. Parent clients/backend restoration remain unqualified.
Log: `.ios-host-tmp/assets-baked-lifecycle-first-20261026.log`;290 original
files/5,762,942 bytes remain in `.ios-host-tmp/tmpncj53r6y`. The exact own Node
census was empty after terminal. These are historical originals, not a live
fixture to reconstruct, retime or resume under a new source identity.

One read-only retained `inspect_directory` profile completed in 4.450 seconds:
all290 original bytes/SHA/device/inode identities unchanged,289 actual original
read memberships. Its largest repeated parent path was Upload.decode14 calls
(3.179/4.433 seconds cumulative), including13 `model_facts.owner` calls;
OriginalFrameStore.read ran2,304 times. This is a function/I/O diagnostic, not
a representative live completion benchmark; a short Photos compatibility run
overlapped its start. SDK/input/Popen/private writes and the stdlib HTTP opener
were blocked. The imported Assets-client HTTP opener alias was not separately
blocked in that first harness; the complete trace contains no client/network
call, but a fully closed HTTP fallback negative is not claimed from it.

The narrow change composes Model.decode's freshly validated creation result
directly into its immediate geometry remainder, avoiding its duplicate
imported→owner→Upload.decode chain. Public facts.geometry retains complete fresh
validation. There is no result cache across calls or mutations, no shared cache
change, no source/candidate/clock/quiet limit change. Focused Model facts/owner,
saved-inode replacement and BakedTree negative cases preceded the newly
justified fresh composition below. No public capability is advertised.

A second duplicated acquisition was identified directly in the ordinary recipe:
RemovalIO.input acquired a full post-input UI, immediately followed by
IOSCreateUI.input's existing fresh after-read. The inner duplicate is removed;
the outer recipe still obtains a new original and adopts the exact ACK/consumed
sequence. No UI result is reused. The timed-out upload WAL had148 of the
unchanged160 permitted frames before context closure, so eliminating those
seven repeated post-input frames also avoids spending the remaining capacity
on duplicate observations. Neither frame nor time limits are increased.

After these narrow changes, ModelFacts6, ModelOwner7 (including actual saved UI
inode replacement) and BakedTree/Baseline8 passed21 cases in86.664 seconds;
`.ios-host-tmp/assets-baked-model-local-composition-20261026.log`. Current-source
guard refusal, foreign owner/domain/URL/time/geometry, unknown/ignored
acceptance and replaced original files still fail closed. Runtime13 (including
the no-input/no-query BakedTree factory), Session7 and InstalledAdmission2
passed22 cases in57.425 seconds;
`.ios-host-tmp/assets-baked-runtime-pure-20261027.log`.

The corrected read-only comparison completed in3.515 seconds on the same290
originals, all exact bytes/SHA/device/inode identities unchanged and289 actual
read memberships. Both actual Assets-client and stdlib HTTP openers, sockets,
SDK/input, Popen and private writes were forbidden. Upload.decode calls reduced
14→8, facts.owner13→7 and OriginalFrameStore.read2,304→1,418; no cached result
survives a call or mutation. These deterministic call reductions are not a
representative live completion benchmark. Artifacts:
`.ios-host-tmp/assets-baked-profile-local-composition-20261026.*` and
`.ios-host-tmp/assets-baked-profile-local-composition-20261027.log`.

The exact before-confirmation admission predicates passed8 cases in0.073
seconds after that tightening;
`.ios-host-tmp/assets-baked-tree-admission-20261027.log`.

The fresh unseeded combined host case then **passed in328.746 seconds** under
the unchanged360s outer limit. It joins actual retained upload bytes, original
implicit bake history, ordinary OFF/ON and a distinct new bake, original parser
input/actual Model UUID, normal namespace Rename/Delete with qualified hidden
output/meta removal, ordinary Model Delete and Home, actual parent read/file
holder quiet retirement and independent backend mapping/blob/meta/worker quiet
restoration. The original picker stays `primary-chosen`. The actual cached
QObject and HFM remain alive after the original lease expires and continue to
block retirement. Pure inspection issues no new input/query and preserves
server-restored responsibility separately from unresolved parsed/resources.
Log: `.ios-host-tmp/assets-baked-lifecycle-local-composition-20261027.log`.
No unchanged whole-case rerun is needed.
The five explicitly selected no-build project suites passed in6.77 seconds;
contract-version and diff whitespace checks also passed.

This proves that declared host component composition, not a native/device,
actor/render/OS or complete shared Assets journey. Next integration must bind
independent actor and rendered-frame sources to the same actual Model and
current context, then establish all remaining cache/texture/decoder/GPU/process
lifetimes. Do not clear caches, reconstruct sources or publish full retirement
from local entity disappearance or server restoration.

Original Assets QML, actual host files/inodes/bytes, binary replies and retained
owner/source WALs execute. The native process, Qt/Create controller, parser,
renderer, AssetServer and oven are explicit SDK boundary models. The fixture
derives recursive deletion from original QML service publication events and
independent actual modeled backend mappings/files; it does not use adapter
expected final rows. No real service, compiler, build or device is started.
Assets capability stays closed and source completion remains 5/14.

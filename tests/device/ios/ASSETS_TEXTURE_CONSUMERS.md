# Original Assets TextureMap and TextureSource sharing groups

History5 adds a bounded `textureOwnership`1 inventory to the literal
History1–4 reader. It observes actual sharing groups reached from accepted
NetworkMaterials, without evaluating GPU getters or retaining product objects
strongly. Host cases pass11/0.257s plus43 earlier facts. The C++ instrumentation
remains uncompiled and unexecuted; this is a source/model packet, not a native
or whole-journey qualification.

## Source and lock order

After actual Geometry registration releases the registry mutex, ModelCache
attaches an observer to each actual NetworkMaterial. Registration, its initial
real map snapshot and later `setTextureMap`, assignment and diagnostic-copy
observations use the existing Material recursive mutex. Callbacks acquire the
registry mutex only in that direction. No registry path enters a Material.
They capture only the original Geometry UUID and actual material slot, never
a Resource, Geometry, Material, TextureMap, NetworkTexture or GPU owner.

The copy observer requires iOS, feature-test compilation and runtime
`--testScript` before any additional source/receiver lock or map scan.
Registration uses those same gates. Existing product copy/assignment behavior
is unchanged, including its pre-existing source-map locking behavior.
Diagnostic callback exceptions or capacity loss make the source incomplete;
they produce no product input or cleanup. Native locking and exception behavior
are source-reviewed only.

The callback reads only `TextureMap::getTextureSource()`, which returns its
sharing pointer. `isDefined`, `getTextureView`, `getGPUTexture` and the texture
operator are never called by the observer. The reviewed source assigns a
TextureSource in two fresh-map `fetchTextureMap` paths before publication to a
Material. This covers those actual paths, not an instrumented arbitrary future
TextureMap source-mutator API or a full transitive decoder/renderer graph.

## Bounded wire and compatibility

The registry stores at most256 weak map/source groups and512 original
Geometry/material-slot/channel/group links. A material has at most32 observer
scopes, each bounded to128 bytes. Group identity uses weak shared-control-block
ownership, never pointer text or URLs. Replacement groups append without
erasing earlier responsibilities. First weak-expiry clocks are immutable.
The revision advances on every actual callback, including repeated/null maps,
and is bounded to1,048,576. Channel-1 marks initial/copy/assignment snapshots,
including an empty material. Repeated links preserve their identity/birth and
update only last-observed clock/revision.

The strict host reader requires actual known material-slot/Geometry membership,
typed nodes, native chronology, bounded revisions and append-only immutable
identities. Complete sources require all nodes to be linked and the current
revision to have a stored observation. First expiry cannot predate the previous
sample that still observed that group alive. Unknown History6, owner
resurrection and missing History5 fields refuse. Existing acquisition/read/
packet limits are unchanged; over-limit packets cannot become successful proof.

The separate `assetModelTextureConsumersVersion1` fact resolves the original
parser/body/Geometry ancestry. Empty/legacy/unlinked inventories cannot prove
texture absence: at least one actual map and source group must be known.
Mesh/material `strong_consumers`1 retains its earlier explicit scope when
reading History5. Normal removal's QObject/HFM/lease result remains available
from validated History5, without texture-retirement authority.

GeometryRelease1 explicitly accepts History3/4; StrongRelease1 explicitly
accepts History4. They reject History5 instead of silently adopting a new
texture mutation context. Their preserved connected passes remain separate;
no old parent or original is upgraded. A connected History5 texture/quiet join
requires a distinct future contract and qualification.

## Host qualification and open duties

Ten focused host cases plus one actual canonical AFC/native-clock carrier case
pass11/0.257s (`assets-texture-five-final-eleven-first-20261027.log`). Real Python
weak references demonstrate independent map/source holders and clone/
replacement groups after a material model is dropped. Counterexamples refuse
foreign/mutable/untyped/oversized/unknown-version history, backdated expiry,
erased/rebound links, revision rollback and wanted absence selectors. The
actual original Probe runs through Node stdin and preserves the source once
per nonce. Native producers, Qt ownership and SDK transport are modeled;
no native parser, compiler, renderer, device or GPU runs.

The regression selection passes23 cases then encounters a loader error from a
misspelled selected Geometry-runtime method. The retained log is
`assets-texture-five-regression43-first-20261027.log`; no adapter case fails.
Only the corrected one-case selection plus the remaining19 cases then run,
passing20/0.348s in
`assets-texture-five-regression-remaining20-first-20261027.log`. These43 old facts
include validated Removal2/3/4/5 and the earlier scoped release contracts.
No unchanged whole flow is repeated.

The five approved no-build project suites pass5/7.04s in
`assets-texture-five-final-common-20261027.log`; contract versions, all880
workspace Markdown files and whitespace also validate. These common checks
do not expand the scenario/native qualification stated above.

`allKnownTextureOwnersGone` means zero strong sharing owners of the selected
original map/source groups. It does not establish completed destructors,
NetworkTexture resources/CPU buffers, ImageReader/KTX jobs, queued image
delivery, GPU operators/buffers/fences, driver or OS allocation, automatic
cache eviction, Actor/peer evidence, backend restoration, source/process or
SDK end. Decoder, destructor, GPU and resource completion flags remain false.
No cache is flushed, product owner released, input repeated or metadata retired.
Assets remains incomplete; overall source completion stays5/14.

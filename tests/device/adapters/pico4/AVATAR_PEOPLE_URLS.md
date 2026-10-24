# Pico Avatar/People: normal URL and native failure subflow

Feature 3/14 remains **partial**. This packet implements the normal Avatar URL
subflow with original native load/failure facts and durable recovery. It does
not enable a `feature.avatar-people.*` capability triple or qualify the complete
15-checkpoint [v16 source contract](../../feature_journeys/AVATAR_SOURCE.md).

## Normal input and source reuse

The fixed read-only Phone source is
`5527d540e99cc6dba4204a5e904a854e6e1cd2b4`. Its generic
`NormalAvatarPeopleControls.h` source/id resolution and `FeatureModelLoads.h`
are reused. No Phone facade, touch transport, mono artifact or moving worktree
is copied. The actual Pico scripts already open `hifi/AvatarApp.qml` and
`hifi/Pal.qml`; existing original QML/product handlers remain unchanged.

`NormalAvatarPeopleControls.h` resolves original QML source URLs and actual
context IDs, requires the original Rectangle base type for page/dialog roots
and a real visual ancestor, and binds finite scene geometry plus actual window
identity into private source tokens. A bounded separate hit traversal refuses
foreign painted/input overlays, clipping, disabled targets and unproven
negative-z ownership. No QObject object name is invented. `NormalControlUi`
and the actual Pico `NavigationUi` use the same ordinary input helper:
original pointer delivery and whole `NativeFieldInput`, never direct QML
handler invocation or a native avatar setter.

`avatar_people_ui.py` projects original references from the existing
`PicoNavigation` transport. Feature controls require actual `inputReady`;
only the existing Home/paging rows use their original enabled/visible native
survey semantics. URL replacement requires the actually focused original
input and exact original reference. The owner restricts replacement to the
current run/ticket resource URL or its captured original URL.

## Original native observations

`FeatureModelLoads` records only actual `Model::setURL`/`loadURLFinished` and
`Avatar::setSkeletonModelURL`/`setModelURLFinished` events behind the dedicated
E2E macro and `--testScript`. It does not start, cancel or complete a request.
Original request generations, epochs and failed events remain append-only,
including a later fallback within the advertised failed Avatar generation.
The helper has 256 events and a finite generation bound.

The private `featurePicoAvatarState` getter uses its own existing bounded
`AudioSettingsQueue` dispatcher, actual GUI/Avatar/Model affinity, lifecycle,
private result location, command nonce and 512-query native inventory. It reads
advertised URL, live configured preference URL/model name, actual Model URL,
independent Avatar/Model load histories, loaded HFM `originalURL`/geometry
identity, Model/Rig/session identity, scale and runtime Hips index. It never
reports a requested URL or an ACK as loaded geometry.

Before the first normal input, a nonblocking original AvatarData lock captures
the actual packed AvatarEntity IDs and opaque original bytes/hash. A busy lock,
null ID, more than 128 rows or more than 64 KiB returns unavailable; none can
supply an empty baseline. The raw storage source is not an entity-tree,
attachment, loaded mesh or pending-operation verdict. No settings, entity data,
permissions, renderer state or native avatar URL is mutated by observation.

Original private JSON bytes and their SHA-256 are retained by `avatar_state.py`
and the owner, preserving actual source IDs/epochs. Both histories, requested
and actual resource URLs, geometry and exact unowned packed storage are checked
independently. A missing-model verdict requires the current advertised failed
generation and the original matching Model failure. A retained A cannot pass;
only actual unavailable geometry or the actual default loaded HFM is admitted.
This native failure source does not yet prove that the product consumed an
HTTP 404. A separate original resource-response join remains required.

## Durable composition and recovery

`PicoAvatarUrls` uses the existing shared Script source lock and private
candidate/process/run-bound CAS journal. Its private binding factory is
`_avatar_urls(target, run, source_lock=held_original_lock)`. The original
adapter-only `PhaseFixtureReader` supplies input authorization only.

The component requires the existing owning normal runtime to have shown the VR
tablet; it refuses a closed or unready tablet before reserving normal input.
The flow actually opens Home/paging/Avatar, focuses/replaces the normal URL,
confirms, then independently observes native effects. Every intent is durable
before dispatch, with its exact normal command recorded at the original
`NativeNavigationIO.before_send` boundary. Fresh original fixture phase and
native/host anchors are checked after the last original SDK guard and final
private write/copy. Neither a frozen native clock nor a new phase permits a
later input. Component and native capacities are not reset or expanded to make
an observation pass.

A stable result requires three seconds on both host and original native clocks,
with at most 500 ms between original samples, inside the existing 20-second
observation deadline. Polling is 250 ms; the owner has 128 source frames and
128 inputs. The initial source must remain independently quiet for three
seconds, be genuinely loaded with settled scale and
matching live configured/advertised URL. URL-only calls preserve the captured
scale and unowned packed storage; unclaimed intervening scale
changes are refused. Version 3 admits only the independently observed owned
Favorite effect described below.

Lost confirmation or final-delivery replies reconcile through new read-only
observations without repeating normal input. An ACK without a native load stays
pending. A later original cleanup ticket can normally cancel an owned URL dialog
and restore the original URL while explicitly retaining earlier unresolved
input tickets. Exact live preference URL/name, original HFM URL, native scale,
Hips/Model/Rig/session identity and packed storage must match for this limited
restoration result. A later cleanup may prove an already restored URL through
read-only observation. It cannot erase the owner or earlier uncertainty.

**The private owner remains retained after URL restoration.** Base cleanup
refuses complete retirement while it exists. Original physical preference bytes,
Qt/V8 context death, native resource/HTTP work, full wearable/bookmark scope,
relationship/backend and peer ownership have not been joined. Normal URL loading
can affect saved avatar preferences; live cache equality is not physical disk
restoration. No product settings fix, direct native setter, forced QObject death
or restart is used to hide these boundaries.

## Host validation and remaining work

Three bounded selectors are registered in the existing Pico catalog:
`avatar-people-native-ui`, `avatar-state-native`, and `avatar-urls-owner`.
The local catalog changes from 106 to 109; integration must preserve other
agents' later additive selectors and mappings.

The UI harness loads the original AvatarApp through a real Qt5 Loader with
`HMD.active=true`, executes the original Pico touch bodies and whole
`NativeFieldInput`, and passes actual QML messages to the complete original
`avatarapp.js` through its normal Tablet signals. Its normal callback reaches
`MyAvatar.useFullAvatarURL` and restores the original URL. The native input
branch, source/window/geometry binding, wrong root base type, uninitialized
page, disabled/foreign/negative-z/clipped controls are checked. Context services,
Tablet boundary, source-root URL, MyAvatar calls and JS timers are declared host
actors. No actual native Model is supplied by this UI harness.

The follow-up also compiles the complete original `NavigationUi::observe`
body and original control-ID/visibility/enabled/token functions with both E2E
and Pico branches enabled. Its real Avatar DTO is checked for readiness,
dialog text and a changed original token after page movement. Unrelated
application services are explicit unavailable host seams. This exposed and
corrected an earlier misplaced Avatar metadata branch and missing dedicated
header include that isolated input-branch compilation had missed. The owning
Qt5 check passed in 7.929 seconds; the same host test, reading only the fixed
Root `d5ad48ed3f` native source including its Browser app branch, passed in
7.689 seconds. Neither check compiles the complete Android application.

A separate Qt5/Qt6 harness compiles the whole original Model/Avatar URL and
callback bodies plus the complete getter/queue, real original storage lock and
original live preference accessors. It checks worker-to-original-slot routing,
failure/unavailable/default fallback, restoration, blocked dispatch, busy/large
storage refusal and the actual 512 cap. Cache/resource/scene/Rig/geometry and
AvatarManager are declared seams. Full native Interface is not compiled here.

The nine host owner tests use the actual canonical binding factories, original
shared Script source lock and PicoNavigation/NativeIO path over
explicit SDK/Qt/model actors, including normal raw paging, matching native
failure versus retained wrong geometry, ignored effects, lost replies, strict
quiet proof, last-guard phase/host-age refusals and retained cleanup ownership.
They supply no native network, render or independent peer/backend facts.
The standalone nine-case owner selection passed in 25.950 seconds; the separate
original native-body test passed with Qt6 in 3.896 seconds. Contract registry,
unchanged v16 inventory, JavaScript syntax, whitespace and workspace
documentation checks also passed. Prepared Qt5 and system Qt6 are local host
checks; they do not substitute for an installed Pico build or device run.

Next executable work is actual bookmark storage/normal save/choose/delete,
scale and wearable/Hips ownership, genuine resource replies and physical
preference restoration, mutual People consent/backend/peer composition,
independent stereo artifact publication and final context/resource retirement.
Pico's original local-self rendering is disabled; later rendered evidence must
use an actual remote avatar/stereo lane without overriding that behavior.
No physical device, ADB/Appium/OpenXR run, dependency installation, service,
Jenkins job or remote write was performed.

## Bookmark and scale continuation

The same private normal-control factory now exposes bounded `save_bookmark`,
`set_scale`, and `bookmark` (choose/delete) flows. Settings use their actual
separate confirmation/cancellation controls; Settings has no original title
property, so no invented title is supplied. An original Favorite confirmation
whose actual label becomes `OVERWRITE` is unavailable to adapter input. The
Qt regression confirms that a duplicate name cannot reach a pointer or change
the original physical file.

The closed Manage-row hit observer recognizes only the original AvatarApp
creation context, original `container`/`favoriteAvatarImage` identities, actual
anchors and real rectangle/plain HiFiGlyphs base types and properties. These
known noninteractive tint/trash decorations fall through to the original row
MouseArea. Qt Quick Text advertises mouse/touch even for the original plain
non-link trash glyph. Actual normal Qt pointer delivery independently reaches
Delete; foreign look-alike tint and glyph components still refuse input. No
product stacking, event handler or component has been changed.

`AvatarBookmarks::e2eBookmarkStorage` reads the actual protected original cache
and its actual `avatarbookmarks.json` without constructing a missing manager.
The fixed Phone storage foundation is strengthened with an owned private
ancestor, stable immediate-parent/file descriptors, no symlink/hardlink or
foreign writable file, bounded raw bytes and actual cache/disk equality.
Absence requires an independently absent file and genuinely empty original
cache. Unknown, busy or mismatched sources never provide an empty baseline.
Raw bytes, their hash, original cache serialization and file revision/path
hashes remain private. The combined result is limited to 245760 bytes so the
existing 262144-byte host envelope limit remains unchanged; oversized originals
are unavailable, not truncated. Native queries remain bounded at 512.

The separate `featurePicoAvatarBookmarks` getter uses a dedicated original
bounded dispatcher, actual manager-thread reads, weak object identity and
request replay refusal. A blocked worker or GUI cannot hang the caller or
publish a timed-out value later. The private host observer is available through
`_avatar_bookmarks_observer`; actual manager replacement invalidates continuity.

The real Qt5 AvatarApp/Pico-pointer/whole-avatarapp.js harness now passes normal
Get/Add/Remove calls through a closed synchronous host IPC to the complete
original native Bookmarks constructor, cache access, Add/Remove and physical
writer bodies. It independently reads the actual file after calls and preserves
an unrelated original bookmark. The latest normal Save → scale 1.5 → reload →
Delete path passed in 10.614 seconds, including duplicate and foreign-decoration
refusal. The native storage/complete getter test passed separately with Qt5
(2.763 seconds) and Qt6 (3.900 seconds), including physical/cache mismatch,
file identity/permissions, blocked dispatch/worker, manager replacement,
absence and the real query cap. No additional catalog selector was added.

Avatar model/scale/wearable services and Script permissions at that UI IPC are
declared host actors. Bookmark-load model completion and its original native
callback lifetime are not supplied by this storage test. The original script
can issue additional bookmark-load callbacks after native change notifications;
all actual host callback calls are retained, without replaying adapter input.
The host timer actor runs original scheduled functions at a declared message
boundary; it does not qualify a real 300-ms delay. The separate native
load/failure source remains the loaded-model authority.

The durable URL owner still permits URL operations only. A durable joined
Bookmark/Scale owner, original physical avatar-preference baseline/restoration,
native bookmark-load callback work and full parent composition remain open.
Normal Settings Save calls other original settings setters as well as scale;
these effects must enter that owner before full cleanup can be qualified. The
original bookmark writer can reformat otherwise unchanged unrelated data:
actual native tests preserve this raw-byte difference instead of claiming exact
physical restoration. This continuation does not enable a capability triple.

## Passive original avatar-preference baseline

The separate private `_avatar_preferences_observer` now reaches the original
`featurePicoAvatarPreferences` getter. It records the actual fixed Avatar and
fullPrivate/Avatar settings, all 23 original MyAvatar preference Handles and
bounded original avatar-entity Handle vectors, actual native live settings,
Manager identity/mutation sequence, original writer birth, and independently
acquired physical JSON row tokens. The existing URL and state source contracts
are unchanged. No capability or additional catalog selector is enabled; the
owning `avatar-state-native` wrapper now includes this third native case.

A baseline never calls a Handle getter: its original `get()`/`maybeInit()` can
initialize the Handle and insert an invalid Manager row for an absent key.
The native-only method reads original initialized/isSet/default/value/deprecated
fields under a barrier stored in the actual existing Manager. Gated mutations
cover Handle set/remove/deprecate/init/deinit and the original Manager mutations;
there is no inline process singleton that could split across shared libraries.
The original headPitch Handle really uses `Avatar/`, while original QSettings
can persist it as `Avatar`. Both original keys remain in their separate sources.
An invalid lazy cache row is excluded from the encoded absence comparison only
with its real initialized, manager-bound, unset Handle evidence.

The source never syncs, reloads, creates or repairs a QSettings object. It reads
the existing original worker on its actual thread through the bounded weak
QObject queue, without a Manager/preference mutex across that queue. A blocked
worker returns within the existing 200-ms queue budget; unfinished original
callbacks stay owned, and their late results are discarded. A worker that has
not actually initialized its original QSettings is unavailable. Runtime
`--testScript`, dedicated E2E/Pico gates, original object affinity, private
lifecycle readiness, finite histories and the unchanged 512-query limit apply.

Original JSON encoding intentionally changes some QVariant types: float and
QUrl can round-trip as double and QString. The source retains every raw typed
cache, writer and Handle QVariant separately and runs the complete original
`writeJSONFile` encoder for the comparison. It independently opens the actual
original JSON path with stable file/parent/private-ancestor checks, refuses
symlinks, hardlinks, unsafe modes, duplicate/alternate canonical JSON, excessive
rows/bytes and unsupported custom serializers, and retains the exact fixed-row
raw tokens, physical file/path hashes and acquisition identity. It never
substitutes a second cached QSettings reader or deserializes a foreign
`@Variant`. Cache-to-writer and writer-to-physical agreement are separate flags;
the strict host `baseline()` refuses either disagreement. Raw originals are
never truncated; the combined private source stays within 245760 bytes.

The complete original native Handle initialization, Manager, WriteWorker,
SettingHelpers/SharedLogging implementation, MyAvatar Handle declarations and
initializer keys, passive MyAvatar method and complete TSI getter run in the
new narrow host test. Application/dependency registry and native avatar/model
live getters are explicit host actors. The test proves real lazy absence,
normal scale persistence, original headPitch normalization, a dirty unsynced
original writer during its own turn, cache-only and physical-only conflicts,
file permission/link/duplicate/size refusal, mutation during acquisition,
blocked/late original work, actual avatar replacement and the actual query cap.
Qt6's standalone translation units explicitly preinclude QIODevice, which the
original SettingHelpers otherwise receives through the application build's
headers; no product source or codec behavior is changed.

Validation: the updated owning Qt5 wrapper passed all three cases in 13.887 s;
the new case also passed Qt6 in 12.557 s. The existing actual native Create
browse-setting/Handle/worker regression passed unchanged assertions in 7.830 s.
The two new registry entries are `native-avatar-preference-storage` and
`pico-avatar-preferences-source`, both current/read version 1.

The passive source is now included in the v2 durable URL admission described
below. A joined Bookmark/Scale owner, exact typed Handle/cache/physical restoration,
original bookmark-load callback retirement and the full fifteen-step parent
remain open. No restore operation or full settings-cleanup claim is provided.


## URL owner v2: pre-input preferences and immutable originals

New private URL owners capture the actual preference source before any normal
input and retain it alongside each independent native Avatar and original UI
sample. Native subject/session and live values must agree across that bracket.
Preparation can resume its read-only pending settling phase: cache/writer and
physical rows must actually agree and remain unchanged for three host seconds
and three original native seconds, with no gap above 500 ms. Earlier unsettled
originals are retained; they never become an absent/default starting value.
The prepared baseline index belongs to the original baseline fixture phase.

Every subsequent URL effect also requires actual cache/writer/physical
agreement and a quiet original preference source. The normal input intent and
final existing NativeNavigationIO before-send callback still recheck the exact
fixture activation, source anchors and root CAS. Retained final copy and CAS
work remain inside the combined native/host age fence. Expired sources or phase
advances cannot publish input, and uncertain input is never sent again.
The parser additionally requires the actual fixed C++ Handle types and names.
Native raw acquisition preflights a bounded closed tree of built-in values;
custom QVariant serializers and excessive depth/nodes/bytes are refused before
QDataStream can execute them. Unknown originals never become a default baseline.

Including these independent raw originals inline reached the unchanged 48-KiB
compressed root limit at frame 70 in a measured normal three-URL host flow.
Owner v2 therefore reuses the immutable content-addressed private blob pattern
from fixed Phone5527: every original frame has its own bounded private record,
while the root stores exact SHA-256 references. Each leaf carries the full
candidate/process/target binding, run and fixture URL. Cold reconstruction
verifies all original payload hashes and owner contexts before reading current
sources. The root 48-KiB pack limit, 64-KiB private-record limit, 128 frames,
512 native requests, finite callbacks and all original freshness limits remain
unchanged. A leaf is never overwritten or truncated to fit. A leaf written
before a lost first root CAS remains owned and blocks base cleanup; its target
key remains in the private name. All leaves remain retained while whole
Avatar/People retirement is unresolved.

An additional warm-owner review found that a parsed-frame cache could reuse
an original leaf without rereading its file. The cache now saves only parsing
and decompression: every cached-reference admission and final input/completion
fence inventories every original through a fresh bounded, no-follow descriptor
read. Device/inode/owner/mode/link count/size/mtime/ctime and the complete raw
file digest must still match the first admitted file. Identical bytes on a new
inode are refused. Missing or changed originals are retained as a failure; the
owner neither recreates nor adopts them. The final phase read, inventory and
retained copy all remain within the original combined host/native age fence.
Three actual warm-file counterexamples (delete, identical replacement and
content change at the last NativeNavigationIO guard) and the normal three-URL
flow passed together in 34.580 seconds. The new case belongs to the existing
fences partition, bringing the disjoint owning inventory to 16 cases without
another selector or timeout change. The earlier 90.56-second measurement
describes the original 15-case selection before this follow-up.

The `pico-avatar-urls-owner` registry now writes version 2 and reads versions 1
and 2. Version 1 files retain their original inline frames and can still be
sampled or reconciled read-only. They cannot prepare, activate or clean up via
new normal input because an original pre-input preference baseline cannot be
recovered retrospectively. Their exact version, source IDs/times, pending
ownership and retained cleanup boundary remain intact.

The enlarged owner regression is divided into `avatar-urls-owner`,
`avatar-urls-recovery`, `avatar-urls-fences` and `avatar-urls-cleanup`. Coverage
checks require every owning case to appear exactly once in those partitions;
no case or assertion is dropped and the normal 120-second per-group timeout is
unchanged. The local catalog has 112 groups. Normal-pointer/native effects,
private persistence and phase races still have explicit SDK/Qt/model actors in
the host owner test; the separate native Qt test remains the storage authority.

Validation on 2026-10-23: the four disjoint groups passed all 15 cases in
90.56 seconds (owner 25.079, recovery 16.270, fences 18.677, cleanup 30.533).
The original Manager/worker/Handle/JSON native test, including the custom
serializer and nested/deep/oversized-value counterexamples, passed with Qt5
in 8.305 seconds and Qt6 in 13.040 seconds. These are host proofs with the
declared application/model seams; no physical device was run.

The URL restored flag describes the observed URL/model subflow. It does not
mean the original persisted preference presence/types or lazy Handle state has
been restored. Exact native-owned CAS restoration, joined Favorites/Scale,
wearables, mutual contact/actor facts, resource consumption, actual remote
stereo evidence and full native/context/callback cleanup remain unfinished.
No full Feature 3 capability is enabled.

## Original bookmark load callback and cached URL

The normal AvatarApp QML and whole original avatarapp.js host pipeline now
forwards Favorite loads into the complete original
`AvatarBookmarks::loadBookmark` / `loadBookmarkInternal` and
`MyAvatar::useFullAvatarURL` C++ bodies. Its existing
`updateCurrentAvatarInBookmarks` QML callback can request the Favorite during
normal UI updates. If the skeleton URL already matches, only the original
MyAvatar branch emits `onLoadComplete`; no model-completion actor emits that
cached event. A highlighted matching Favorite is not force-clicked. Different
URLs still use an explicitly declared model-completion actor in this host
pipeline, and wearable clear/add/scale live services remain declared actors.
This proves the original input/callback route, not downloaded model geometry,
wearable effects, remote pixels or persisted preference restoration.

The dedicated passive `featurePicoAvatarBookmarkLoads` getter, closed probe
action `feature-pico-avatar-bookmark-loads-observe` and private
`_avatar_bookmark_loads_observer` expose the actual original registration and
callback metadata. They use their own existing bounded weak queue, strict
512-request history, original Manager identity and a fresh source bracket.
The native collector retains at most 128 registrations. Overflow makes the
observation unavailable without changing ordinary product loading. It never
disconnects, emits, replays, cancels or completes a product callback.

Each row records an original registration ID/time, name/URL hashes, the
original Avatar load-history instance and session UUID, actual Qt connection
and disconnect results, entry/return times and active dispatch count. The
`bookmarkScale` and `bookmarkEntities` fields describe the selected bookmark
arguments; they are not observed effects. Independent Avatar state and actual
preference sources must supply effect evidence. Callback entry/exit metadata
is mutex-protected, including an explicit fact about original thread affinity.
The raw observer/parser keeps the exact append-only history and refuses
replacements or regressions. The two new version-1 contracts are
`native-avatar-bookmark-loads` and `pico-avatar-bookmark-loads-source`.

`captureAlive` follows a weak marker captured by the original contextless Qt
functor. The observer adds no strong Avatar, connection or QObject reference.
Marker expiration is deliberately separate from whole-functor/resource/task
retirement. The native Qt test proves that the original pending functor itself
holds MyAvatar alive, that the original callback disconnects before effects,
and that a subsequent original signal does not repeat those effects. After
the real callback and release of the declared application/model references,
the actual original QObject QPointer becomes null. It also observes an active
callback from the original bookmarkLoaded signal and rejects late observer
results from blocked dispatch and Manager-worker queues. The Manager-worker
affinity move is a diagnostic host seam, not a claim about product affinity.

Fixed Phone5527 was inspected again for the reusable route. Its original
bookmark C++ connection has no finished capture/dispatch observation source;
the new Pico source therefore instruments that existing common C++ body only
under the dedicated Pico/E2E gates and runtime `--testScript`. Phone facade,
touch and mono evidence are not copied. The existing UI and native-state
owning selectors retain their names; the latter now includes the dedicated
original callback case. Joined durable Favorite/Scale ownership, exact typed
native restoration and whole Avatar/People retirement remain unfinished.

Validation on 2026-10-23: the original QML/whole-JS/native-load pipeline passed
in 10.471 seconds. The dedicated original-call/real-Qt/blocked-queue case
passed through its owning wrapper with Qt5 in 2.877 seconds and directly with
Qt6 in 3.845 seconds. Both disabled runtime admission and active `--testScript`
were executed. The full Android application was not built and no physical
device or OpenXR session was run.

## Durable normal Favorite/Scale composition

The private `_avatar_favorites` factory now composes the existing normal
Favorite and Scale controls with four independent original sources: Avatar
load/geometry state, native Handle/cache/writer/physical preferences, bookmark
cache/raw physical file, and original Qt bookmark callback history. Its
version-1 owner records exact phase tickets, original before-input controls,
once/token envelopes and published native commands. Every effect requires
three seconds of unchanged observed source and host time, with observations
at most 500 ms apart. An acknowledgement or a selected bookmark argument is
never accepted as the actual loaded avatar or scale.

The new owner admits only the fixture's exact `e2e-<run>` name and scale 1.5.
The original Favorite load clears worn avatar entities, and the QML may load
a newly saved Favorite during its ordinary update. Therefore even Save
requires absent unowned live AvatarEntity storage, zero actual native ID/data
vectors and count Handle, and no persisted indexed rows or nonzero persisted
array size. A lazy empty Handle cannot replace the actual cache, writer or
physical baseline. The owner preserves every unrelated bookmark and checks
the same target/run/candidate/fixture and current Avatar identity throughout.

URL-owner version 3 can consume a Favorite effect only through a bounded
immutable historical proof. It validates the original phase prefix, actual
input controls/commands, four-source quiet interval, previous URL-owned
subject and exact original preference source, and the current
native/preferences subject. A foreign preference change before the Favorite
operation cannot be adopted through its later effect proof. If an earlier
normal Favorite operation changes lazy preference presence or native mutation
sequence, a further independently joined receipt is required; this packet
conservatively refuses rather than adopting that change. This admits the observed
Scale 1.5 before the missing URL and the observed Choose of A before normal
URL Restore. Version 2 retains its existing strict behavior; version 1 stays
read-only. Neither version adopts a new baseline, changes a native source
packet or substitutes an expected scale for an observed effect.

Both owners use the same private immutable-frame acquisition implementation.
Warm caches retain parsing only: every final input and completion fence
rereads the full bounded original leaves and checks descriptor identity,
permissions, stamps and bytes. The Favorite owner repeats exact phase/root
checks after native acquisition and before the original writer. Losing the
result of an already consumed Scale confirmation leaves the ticket pending;
cold reconcile only observes and never publishes the input again. All
existing limits remain: 128 frames, 512 native requests, 48 KiB packed payload
and 64 KiB private file; no timeout or source-freshness threshold was raised.

`avatar-favorites-owner` runs the composed Save, Scale, missing URL, Choose,
Restore, Delete and retained cleanup path. `avatar-favorites-fences` owns the
lost-result, final native-guard phase advance, unowned live attachment and
persisted-size and foreign-preference counterexamples. These host cases use the real canonical
binding, SDK/native navigation, source readers, phase journal and private
CAS, with explicit Qt/model/storage DTO actors. Original QML/JS/C++/Qt source
qualification remains in the separate existing native owning tests. The host
journey is not a physical Pico run, downloaded-model or stereo/render proof.

Deleting the owned bookmark and restoring live scale/URI does not establish
exact original native Handle types/presence, JSON file bytes, QML contexts,
Qt functor/Model resources or task retirement. The original snapshots and
owners remain retained, and base cleanup refuses while they survive. A
native exact settings/bookmark CAS restore, owned Wearables, contacts/peer
and stereo evidence are still open. Full Feature 3 capability remains off.

Validation on 2026-10-23: the final two new owning selectors passed all six
cases in 89.45 seconds (composed owner 54.257 seconds; fences/recovery 35.192
seconds), within each unchanged 120-second selector limit. The foreign
preference case first validates the full observed effect and current native
subject, asserts the exact physical-row difference, then checks the typed
inner admission refusal before the shared source lock can mask errors. A
reference error caught by an earlier final rerun was corrected before this
passing run. The unchanged version-2 strict-scale countercase passed in
6.146 seconds, and all three warm immutable-leaf mutation counterexamples
passed in 4.810 seconds. The local catalog gains exactly two selectors; its
local count is 114. Integration must preserve newer additive Root entries.


## Normal cached Favorite and original preference receipts (2026-10-24)

The existing `avatar-people-native-ui` owning case now joins the same normal
AvatarApp.qml/Pico pointer/whole avatarapp.js route to the original Bookmarks
load and cached `MyAvatar::useFullAvatarURL` branch, actual Qt connection and
whole callback. Its Scale call executes the complete original
`MyAvatar::setAvatarScale` and `AvatarData::setTargetScale` clamp with the
original timestamp body. Its empty clear executes complete original
`MyAvatar::clearWornAvatarEntities` over the real ReadWriteLockable and packed
map. A nonempty wearable removal is unavailable, not silently cleared.

The same existing Avatar instance also supplies the full original
`featurePicoAvatarPreferences` getter, original Handle declarations/initializer
keys and passive `e2ePreferenceHandles` body. The original Manager, WriteWorker,
JSON encoder, barrier and independent physical reader run in that process.
`native_preferences_support.py` shares the identical source preparation with
the existing `AvatarPreferencesNativeTests`; it does not add another preference
getter or a parallel journey. Unrelated NavigationUi services retain their
separate unavailable registry. The owning observer now includes the actual
AssetsUiInventory header used by the complete original NavigationUi source.

Every Favorite callback pair retains the actual normal input command, original
control token/inventory/reply, QML-to-JS message batch, native PID, unique
preference request/sequence, Avatar/session and callback row. Before and after
snapshots independently preserve all typed Handle/default/presence values,
cache and writer rows/encoded rows, barrier mutation sequence, physical file
identity/hash and the complete original Settings bytes. The native getter's
nonce-replay refusal and the callback's one dispatch, completed disconnect,
zero active entries and dead weak functor capture are checked separately.

The final narrow native case passed in 15.283 seconds under the unchanged
90-second combined moc/compile/link and 120-second outer bounds. It observed
four callback pairs: three cached originals and one explicitly declared model
completion. All 23 observed Handles remained uninitialized, cache and writer
Avatar rows remained absent, and all paired Settings bytes and mutation
sequences were unchanged. No Handle read/write is inserted to manufacture a
lazy effect. The noncached model setter remains an actor and does not qualify
original URL persistence. The shared preparer's existing native preference
case also passed in 7.964 seconds, including its actual lazy get/set, dirty
writer, foreign physical bytes, normalization, late-result and replacement
counterexamples. Full inputs, raw streams and generated stages were retained;
no source changed during either run. An initial missing original inventory
header compile failure remains retained rather than counted as a pass.

At this initial native-only checkpoint these were source witnesses in the
existing UI case. They did not yet add the shared raw admission rule below or
qualify retained cleanup.
Actual loaded Model/renderer/EntityTree/V8/Android ownership, the whole live
scale renderer, 3-second final owner quiet, raw Handle/cache/writer/physical
Settings and bookmark byte CAS restoration/retirement, Wearables, contacts,
peer/stereo and device evidence remain open. No cache clearing, process exit
or no-change snapshot supplies their missing release. There is no new selector
or persistent owner/source format, and no compatibility version changed.

The committed Phone Avatar reference inspected read-only was
`7db55e538899bfbc2d73a7741e49ec31ebb9c004`. Its control/runtime actors and native
DTO validation do not provide this original Handle/Manager/WriteWorker/JSON
join. No Phone UI assumption, moving WIP import or Phone modification is used.


## Existing v16 cached preference admission

The same native UI case now compiles and executes the complete unchanged
`NavigationUi::observe` and `NavigationUi::apply`. Its normal Favorite inputs
retain the actual bridge ID, UUID command, consumed sequence, generation and
control token used by the existing PicoNavigation protocol. The former
isolated Avatar-dispatch fragment is removed. The complete original source
preparer is shared with Assets; its generated Assets bytes remain identical.
Actual Places helpers are enabled only in this Avatar host profile, preserving
the other host profiles' existing unavailable service seams.

`avatar_favorite_effect.unchanged_preferences` now supplies one strict rule
for the actual cached/Scale behavior. Both the native UI's real TSI pairs and
the existing Favorite owner `matches` and historical `effect_proof` validation
use it. Every typed Handle/default/presence/binding, Manager mutation sequence,
cache row, writer identity/row, complete physical file identity/hash/rows and
all live fields except the independently checked scale/targetScale must stay
unchanged. No missing value or expected default substitutes for an original.
The ordinary four-reader frame acquisition, immutable archives, phase fences
and URL3 adoption remain the existing implementation; no historical host JSON
is inserted as a fresh owner sample, and no parallel journey/getter is added.

The old test DTO incorrectly made the persisted scale Handle follow each live
scale change. It now retains its persisted value, matching the compiled
original MyAvatar/AvatarData methods. A new existing-owner countercase changes
coherent raw preferences during the consumed cached Favorite callback. The
callback completes once, but the typed inner admission rejects settlement and
keeps the pending owner and foreign value intact. Existing before-input foreign
preference and lost-result/no-resend fences remain covered.

Final native admission passed one case in 23.866 seconds; the complete existing
Save/Scale/missing/Choose/Restore/Delete/retained-cleanup owner passed in 53.745
seconds, the new raw-change countercase in 8.997 seconds, and the two affected
legacy fences in 24.688 seconds. The changed existing preference-native case
also passed in 8.100 seconds: its actual lazy get and persisted set produce
independently valid raw changes that this same rule explicitly refuses. Each
retained its full frozen source manifest
and original output under the unchanged 90-second combined native build and
120-second per-selection bounds. Separate historical compatibility validation
accepted all 45 original Full-Navigation snapshots without changing bytes;
this was a codec check, not a new native query or freshness proof. Initial
missing-Places-helper and incorrect old disabled-gate harness failures remain
retained. The catalogue gains no selector; its existing Favorite fence group
owns the one added case. Existing closed data formats and versions are intact.

The normal cached/no-change source connection is now present in the existing
owner. Exact native Handle/cache/writer/physical Settings and bookmark byte
restoration still needs its owned CAS and final quiet/retirement. A normal URL
write can initialize a previously lazy Handle; ordinary `remove()` cannot undo
that initialization or Manager binding. The Create browse-setting owner also
explicitly refuses live cached Handles. Neither helper authorizes a simulated
raw restore. Noncached original model persistence, whole Model/renderer/
EntityTree/V8/Android ownership, Wearables, contacts, peer/stereo and devices
remain unqualified. The shared owner tests retain their declared SDK/Qt/model
DTO boundaries; retained fixture copies are historical originals, not live
source identities or retirement proof. Full Feature 3 remains unavailable.


## Integrated Root verification

Root selected the two fixed cached-preference packets as `73cb3556e1` and
`e6cc3fbfc5`, preserving all fourteen coverage rows and the 249-selector catalog.
Fresh tests on that integrated tree passed the original native UI in 23.305 s,
the complete existing Favorite owner in 53.062 s, all six Favorite fences in
38.576 s, and coverage in 0.090 s. The original preference-native case passed
separately in 7.919 s, including actual baseline-valid Handle changes refused
by the same no-change rule. All 13,546 tracked/new source files retained their
complete before/after hashes throughout these tests. Original native stages,
raw streams and owner fixture originals remain in the private Root archive
under `avatar-cached-raw-*20261024`.

The actual native result retains 45 normal inputs and four original callback
pairs: three cached callbacks and one explicitly declared Model completion.
Four repository suites passed in 2.60 s; contract-version and whitespace checks
also passed. Existing 90-second native compile/link and 120-second owning
selection bounds were retained. These results verify the shared cached/Scale
admission, not the open native restoration, whole ownership or device scope.
Feature 3 remains partial.


## Exact original data and actual no-op end observation

Cleanup in the existing Favorite owner now requires the independently acquired
original typed Handle values/defaults/presence/bindings, raw Manager rows,
actual writer variants/encoded rows, whole Settings file hash and exact
Bookmark/cache bytes. The original live URL/model-name/scale and loaded
resource URL must also match the captured baseline. Semantic map equality,
a successful Delete or default-value reconstruction cannot stand in for bytes.
This is a strict completion predicate, not an additional getter or write path.
A differing original remains owned; no raw mutator or unlink is implemented in
this checkpoint.

The same data predicates qualify the existing native normal UI case. It
captures real original preference and Bookmark data before the normal flow,
then records independent end samples from the actual TSI/Handle/Manager/
WriteWorker/physical reader and original Bookmark/cache/callback sources.
The registered private `pico-avatar-original-data-quiet-host` v1 trace has a
closed shape. The existing native trace collector immediately reads every
original line and records its SHA-256, actual host monotonic time and epoch.
The producer waits for those real host receipts and actual native observations
to span at least 3000 ms; it never substitutes a time margin, expected baseline
or a requested state. Every source and actual host receipt must remain within
1500 ms, with native and host sampling gaps no larger than 500 ms. Complete
Settings bytes are independently tied to the TSI's whole-file hash.

Final native validation passed in 28.652 seconds. Fourteen actual end frames
span 3346.867 ms on the native monotonic clock and 3338.978 ms on the independent
host clock. Preference/Bookmark/callback epochs span 3346/3347/3347 ms; the
largest native/host gaps are 263.904/262.551 ms. All 23 observed lazy Handles
and every mutation sequence remain unchanged, complete Settings bytes remain
original, and the normal original Delete has restored complete Bookmark and
cache bytes. Its actual new file revision is retained separately; no old inode
or timestamp is asserted to return. The first actual frame, unchanged, is
explicitly refused as current evidence at the last measured native epoch.
The original trace is 234121 bytes, within unchanged 512-frame/16-MiB bounds.
Combined native build, per-native runtime and outer selection limits remain
90/30/120 seconds.

The affected existing full Favorite owner case passed in 54.466 seconds. Real
preference-native get/set originals remain independently valid but fail the
same original-data predicate (8.619 seconds). The existing real Bookmark-native
case also demonstrates the important opposite: its normal original writer
canonicalizes a noncanonical starting file. The map is restored but the raw
bytes differ, so the new original-data predicate correctly refuses completion
(2.889 seconds). No restore is manufactured for that negative case. Full
original streams/generated stages, all source freezes and independent host
receipts are retained. Fixture process/worker shutdown occurs after the measured
window and supplies no retirement evidence.

This native end observation qualifies the scoped Settings/Bookmark no-op data
condition. The surrounding MyAvatar/model initialization and JS/native model
endpoints remain declared host actors; no complete Model/renderer/V8/Qt heap,
EntityTree, peer/stereo or device verdict follows. The Favorite and URL owners
remain retained. Observed raw differences still need original native Mementos,
typed Handle/Manager and real worker/file CAS with durable intent/result
receipts, then actual quiet and owned retirement. No mutation sequence may be
rolled back, no unowned row may be overwritten, and no cache deletion or process
exit replaces restoration. Full Feature 3 remains unavailable.


## Root original-data and native restore-join verification

Root selected the no-op packet as `4e8b1b59cf` and the normal native URL/Scale
IPC join as `64eb6f9a35`. Root review additionally found that original-data
equality omitted the full native live object. A new genuine original-getter
counter changes its declared live collision-sound value while every real
Handle, Manager/worker row and whole file stays unchanged. It was red in9.348 s
and green in10.083 s after `b1142820ea` requires every original live field.
The normal Scale no-change predicate retains its own intended semantics.

The stronger rule also exposed an old declared native/JS live-owner mismatch.
Normal original avatarapp.js URL/Scale calls now reach the same native Avatar
through the existing IPC and whole original methods. Initial loaded-avatar
context is explicitly admitted through that original URL method before the
first baseline; full MyAvatar startup/model setting remains a declared actor.
Bookmark callbacks no longer inject a native URL/scale before load or send a
second native input while updating the JS mirror. Independent before/after
preference originals accompany each normal native call.

The final integrated NativeUI case passes in32.398 s with full original live
data equality and21 actual native/host end frames (5.160s native,5.157s host). Genuine native/host
monotonic and epoch sequences must have nonnegative gaps at most500ms; reversed
actual original records are refused without inventing a timestamp. Native
preference cursors also remain strictly continuous. The existing Favorite
owner passes in63.823 s and the native Bookmark byte-difference case in3.028 s.
All13,558 tracked/new source hashes remain unchanged during each selection.
Full native stages, raw streams, host receipts and exact clocks remain private
under Root's `avatar-normal-native-restore-*20261024` records.

These are scoped data/no-op and normal native input results. No Settings write
was inserted to manufacture a restore. Native model completion/initialization,
whole resource release, raw mutation CAS and final ownership retirement remain
open. The complete feature is still partial.

## Original normal setter restoration and warm lazy Handle CAS

The complete original-live comparison added after the checkpoint above exposed
a real host join gap: the native preference URL began empty and ended at the
owned avatar, while ordinary restore input reached only the JS Avatar actor.
That preserved run is refused; its original streams are not retimed or repaired.
The existing normal UI case now joins ordinary `avatarapp.js` URL/Scale calls
through the same IPC to the complete original native `useFullAvatarURL` and
`setAvatarScale` bodies. Native Bookmark load replies update only the JS mirror;
they do not execute a second native setter. Per-load direct native URL/Scale
assignments are removed. Initial loaded-avatar admission uses the actual URL
method before the original baseline, without initializing a Setting Handle.
Complete MyAvatar startup and the model setter remain declared host boundaries.

This separate normal join passes in 32.901 seconds: seven actual native URL and
two Scale inputs have independent original preference pairs. Four original
Bookmark callbacks include three cached completions and one declared model
completion. All 23 lazy Handles and the mutation sequence remain unchanged;
complete original live values, Settings bytes and Bookmark/cache bytes return.
Fourteen real end frames span 3343.299 ms native and 3342.995 ms host. The full
live comparison includes collisions, collision sound and animation overrides;
all native, host and source chronology gaps must be nonnegative and bounded.

The same original `AvatarPreferenceSnapshot` now retains a private typed warm
Handle memento, bound to the actual Avatar QObject, Handle, Manager, weak
binding, all registrations and typed cache rows. It reuses the original passive
Handle getter; no script-supplied QVariant replacement or additional getter is
introduced. The normal cached Favorite continues to be a no-op, with its actual
URL Handle memento compared at each native end sample. With this connection,
the owning native UI case passes in 30.615 seconds with 14 real frames spanning
3370.602 ms native and 3364.348 ms host. Its separate mutator is not invoked.

The deliberately narrower `restoreUnwrittenLazy` operation can undo only an
observed lazy initialization whose worker and full physical file have not
changed. It compares the current actual registration/cache/Handle and audit
sequence under the same original Manager barrier before restoring original
typed fields and absence. It never calls get/remove/deinit as an undo, emits
no Settings write, touches no unowned row, and never decrements the sequence.
A changed or written value is refused. Copies share one attempted transaction;
lost intent/result answers remain owned and do not authorize replay.

The existing native preference selection passes in 11.038 seconds, including
real get initialization, stale and foreign-registration refusals, lost intent,
actual restoration with lost result, and written-state refusal. An actual
original Handle remove no-op during the durable intent increments only the
audit sequence; atomic sequence CAS refuses that transaction even though the
data are unchanged. Six actual fsync'd intent/result originals use registered
private `pico-avatar-lazy-handle-cas-host` v1, each bounded by 64 KiB. They are
cold-read and fully reread through the existing `ClosedOriginalFile` owner;
independent original TSI snapshots, rather than journal Booleans, qualify data.
The earlier protected-call compiler failure and full-live URL refusal remain
retained. No unchanged retries, budget increases or full Quick selection occur.

These are connected source/host partial results. Warm lazy-only CAS does not
restore a real set/save or normalize noncanonical Bookmark bytes. Actual
noncached model persistence, typed worker/file and Bookmark byte CAS, final
quiet/archive retirement, full Model/EntityTree/renderer ownership, Wearables,
People/peer/stereo and device qualification remain open. Phone fixed source
`a7be274da152b9d0b77e2fe5bb9874c5b1e18a31` was compared read-only for its
durable intent, participant restore and final journal-CAS ordering; its Pal UI
preferences do not provide this raw lazy Handle memento. No Common18, Phone
input/mono, graphics or moving work-in-progress sources are imported.

The subsequent native affinity/age review is closed in a separate narrow
followup. Both remembering and restoring reject a foreign caller before any
saved Handle-key or Avatar dereference, and require the actual Avatar/Manager
GUI affinities. Each current memento starts its own real `QElapsedTimer` before
capture. Expected and actual timers must still be within 1500 ms after the
durable intent, immediately before and inside the atomic GUI CAS; no timer is
reset by journaling. Wall-clock freshness remains an additional requirement.
Historical original data comparisons do not gain an artificial age restriction.
The same native preference case passes in 13.193 seconds with the existing
20/60/12/120-second moc/build/runtime/outer limits. A real foreign `std::thread`
reaches neither getter nor journal. A real 1501-ms durable-intent delay is
refused without a field mutation or CAS audit increment. Eight actual journal
originals retain both refusal pairs, the genuine restore and lost-result proof.
An additional actual owner-destruction-during-intent counter retains its ninth
original intent without manufacturing a result; it refuses the saved Handle
before dereferencing it and cannot replay. Owner/Manager GUI affinity is checked
again after the durable callback. Original destructor Settings effects remain
actual observations, never a successful CAS or final retirement claim.
No clock value is forged and the main no-op case is not repeated. The earlier
12.952-second thread/age selection is preserved separately.

Root selected the typed memento packet as `4b35ab2c5a` and its native GUI/age
followup as `626e5f5e78`. The fresh integrated original native preference case
passes in13.145s (14.974s including source hashing and the outer invocation),
with all13,574 source files unchanged. Compilation retains the original
20-second moc/60-second compiler limits and actual native execution its
12-second limit; the outer selection remains120seconds. All nine exclusive
fsync'd intent/result files are cold-read and fully reread. The original
destroyed-owner intent remains owned without a fabricated result. The native
stages, binaries and stdout/stderr remain in the private
`avatar-lazy-cas-root-native-20261024-*` artifact directory. This does not qualify
written Settings/Bookmark restoration, real model loading or full retirement.

## Actual model-setter preference writes and normal data return

The two native UI selectors are now disjoint. `avatar-people-native-ui` names
only the existing no-op method. `avatar-persistence-native-ui` names only
`test_original_avatar_model_setter_settings_write_and_normal_data_restore`.
Each keeps its own 90-second combined moc/build/link, 30-second native and
120-second outer limits. Running the file without a method would discover both;
the catalog does not do that or run either method twice.

The new profile executes complete original `MyAvatar::setSkeletonModelURL`
and `saveAvatarUrl` callers rather than injecting a save into a model stub.
Initial normal URL admission runs before baseline capture: the actual URL
Handle is initialized/set/Manager-bound, the other 22 remain as observed,
and whole real Settings bytes contain the original empty persisted URL.
Base Avatar, Skeleton/geometry inputs, scene and animation initialization are
declared host actors. Their getters never qualify loaded HFM, actual rendering
or the complete MyAvatar startup. The original preference getter's complete
native-data lambda is reused verbatim for private mementos and input guards.

Every normal input and native callback entry fences the last actual owned
memento. Actual unrelated typed cache/registrations, handles, live values and
whole JSON rows remain guarded before adoption of an ordinary setter effect.
Source queries wait only for actual cache/writer/physical agreement, retaining
unready originals with existing bounds. No observer calls sync, reload or
forceSave after normal input. A private fsync'd observation journal immediately
preserves every public preference original and actual model-connection sample,
including before a later failure. Its closed private format is registered as
`pico-avatar-observation-journal-native` v1 and is cold-read through the existing
native descriptor owner; it is historical audit, not a fresh source substitute.

Pico E2E-only passive hooks observe the original setter's actual
`skeletonConnection` shared capture. They retain weak captures and QPointers,
record actual dispatch/return/disconnect and owner-thread facts, and never keep
a callback or QObject alive. The native-only original getter reports registered
`pico-avatar-model-connections-native` v1. The persistence quiet trace writes
private original-data v2 with that additional source; the existing no-op keeps
v1 unchanged. The reader and registry retain v1/v2 explicitly.

The first fresh run is preserved red after 23.043 seconds: the JS native-result
mirror emitted the URL signal before installing the already received new Scale,
so a synchronous original script read observed a hybrid tuple. Only this test
proxy was corrected to commit both actual native reply values before signals;
the product script and strict native guard remain unchanged. The changed
persistence case passes in 37.771 seconds. Its original audit sequence advances
4 to 20, while normal return restores the exact original typed URL Handle,
registration/cache/writer data and whole 89-byte Settings file. Its actual new
inode and timestamps remain recorded. No extra CAS write or sequence rollback
is performed. All nine actual setter Qt callbacks dispatch once, complete and
disconnect; their original shared captures are weak-dead while their actual
caller/sender QObjects remain alive.

Nineteen actual quiet frames span 4828.723 ms native and 4822.916 ms host;
all original 1500-ms freshness and 500-ms cadence bounds remain. The run retains
92 immediate observation records (773060 bytes), a 1272999-byte native report
and 401684-byte quiet trace; no unready sample occurred in this run. Four actual
Bookmark callbacks, nine native calls and 45 normal input guards are retained.
The specifically affected old no-op method also passes in 30.664 seconds:
all 23 Handles remain lazy, audit remains 0 to 0, physical identity remains
unchanged and its 14-frame trace remains v1. No full suite or duplicate selector
is used. These source/host partials still require actual parent/actor/v16
adoption, noncanonical Bookmark-byte restoration where needed, final owned
retirement, complete Model/Renderer/EntityTree, Wearables, People/peer/stereo
and device qualification. Neither callback markers nor fixture shutdown supply
those missing qualifications.


## Common-v16 parent with fresh original native sources

The [source parent continuation](AVATAR_PARENT_SOURCE.md) now joins existing
URL3/Favorites1 through actual `Journey.call`/`OverteSession`/canonical routing.
Fresh native Preference and model-connection sources accompany normal A, Save's
actual original cached callback, normal original URL return and Favorite cleanup.
Exact original data returns; the parent and children remain retained. Complete
observation/actor/capability, genuine Model/renderer/EntityTree/Wearables/People/
peer/stereo and final release remain open. The larger new native integration's
explicit service60/total120 bounds do not alter the existing no-op/persistence30
or any source/operation/quiet deadline. See that continuation for actual red and
green evidence, source seams and frozen Phone reconciliation.

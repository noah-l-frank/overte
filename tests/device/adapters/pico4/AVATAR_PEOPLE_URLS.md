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
scale and unowned packed storage; this partial owner refuses intervening scale
changes instead of adopting them as a new baseline.

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

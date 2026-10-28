# Observed Chat QML compiler, cache and root sources

Feature 10 remains partial. This packet adds a passive direct-unit source to the
existing iOS observation transport. It enables no complete Chat capability and
does not admit an installed Qt binary or imported QML/JavaScript dependencies.
Native code and its dedicated CMake linkage remain uncompiled; no device ran.

## Actual producer boundary

The [OffscreenSurface hooks](../../../libraries/qml/src/qml/OffscreenSurface.cpp)
reserve an observer ticket immediately before the existing `QQmlComponent`
constructor, attach that actual component afterwards, and observe its actual
object only after the existing `completeCreate`. Original loading, callbacks,
ownership, error results and cache behavior are unchanged.

[IOSQmlSourceObservation](../../../libraries/qml/src/qml/IOSQmlSourceObservation.cpp)
is active only for iOS, both existing dedicated test definitions,
`--testScript`, and the patched Qt 6.11.1 version-one binary API described in
[the source-boundary audit](CHAT_QML_SOURCE_BOUNDARY.md). The existing QML
target links its private Qt dependency only in that test configuration. An
unpatched/missing private SDK supplies no observation. The matching patched SDK
and all its private consumers still require one consistent rebuild; nothing
was applied, installed or built here.

The observer retains at most 64 actual Chat load tickets in memory. Root,
creation context, object context and component references are weak. It never
stores a strong Qt compilation-unit holder, invokes a QML handler, changes a
source URL, clears a cache or configures a development override. Opaque source
association remains unavailable. Successfully created roots with unavailable
code association still participate in ambiguity checks. The native read cannot
silently choose a convenient root or create a Tablet through its getter.

Final completion compares the actual object's executable unit to its exact
component through the patched Qt binary. Later reads check that original
receipt against the same live object unit and original contexts again, after
the original component may already have been destroyed. Stored load clocks,
context URLs, object IDs, source/code-unit digests, mutation generation and
compiler clocks remain unchanged. Fresh reads do not retime a historical load.
Context IDs are scoped to this load, not a cross-load global identity table.

## Existing transport and strict reader

The fixed `feature-ios-chat-qml-sources` request has exactly `schemaVersion:1`,
`commandId:ios-<32hex>`, `action` and `runId:<32hex>`. It accepts no URL, digest,
object selector, expected result, cache mode or replacement input. The actual
[probe](../probe/overte_e2e_probe.js) consumes each nonce once before invoking
the native hook and writes the unchanged original to
`feature-ios-chat-qml-sources.json`, using the existing private atomic compact
writer. Missing SDK/hooks and thrown native reads remain unavailable. A lost
file-save return cannot trigger a second native invocation.

The existing [bound factory](adapters/feature_observation.py) exposes
`chat_qml_sources(clock_source=...)` over the same authenticated HTTP/AFC
session, candidate, foreground process, result directory and native clock.
It creates no process or SDK session. The existing 1.5-second/61-read acquisition
bound, 250-ms native clock agreement and process/candidate guards apply. The
source has a 64-KiB transport ceiling and a 32-KiB native unit-receipt ceiling.

The [typed reader](adapters/chat_qml_sources.py) validates the version-one Qt
compiler input, actual load and independent current read envelopes. It requires
the same PID, chronological original source/compiler/load epochs, consistent
native load clocks, bounded immutable unit data and generation, exact direct
compiler/output digest agreement, and the actual component/source URL join.
Reading the same root preserves its entire original load receipt. A replacement
needs a different object/load identity, advancing loader/Qt counters and its own
later compiler input; an old cached receipt cannot become a new load.

`admit_direct_unit` compares the observed decoded UTF-16-LE code-unit count and
digest against [reviewed repository pins](chat-qml-source-pins.v1.json) and an
independently supplied source location. It admits only this direct unit.
`pageControlSourceSha256` is the separately measured current normal-control
fingerprint; it does not substitute for a complete input/owner WAL association.

## Qualification and remaining integration

Twelve new host cases pass in 0.330 seconds: six strict pin/source/clock/lifetime
semantics, one actual JavaScript dispatch including uncertain native/save
returns, and five existing HTTP/AFC factory cases for actual candidate/process
guards, unchanged originals, unavailable sources and lost HTTP return. Native
Qt/compiler/installed-byte producers in these tests are explicit models.
The extra recovery countercase first reads a valid original, then refuses a
later unavailable observation instead of returning the previous good receipt.
The uncompiled C++ source also contains an allocation-free sticky failure latch
for every diagnostic catch; a missed second registration cannot silently leave
its earlier root eligible. That native latch was reviewed, not executed.
Log: `.ios-host-tmp/chat-qml-source-final-20261027.log`.
Sixteen existing submitted-Script-source/transport cases pass in 0.311 seconds;
log: `.ios-host-tmp/chat-qml-source-legacy-regression-20261027.log`.
These are logic/transport results, not a compiled hook or product effect.

## Cached-unit and installed-file connection

The separate cached-unit path now joins the actual pre-save compiler owner and
generation to the original QSaveFile handle, successful write/commit and actual
mapper FD/bytes. The temporary StaticData write digest remains distinct from
the pre-save compiler-unit digest. Static mapper copies carry their original
mapping identity; a filename, equal digest or new load cannot create that
association. The existing direct-unit v1 reader remains available.

The owning-thread object/component getter compares actual executable-unit
identity and weak object lifetimes around two current unit reads. Loaded-source
v2 preserves its original load-time receipt and takes a separate fresh unit
receipt on each query. Compiler/write/map clocks remain historical. No strong
product-unit reference, cache clearing or replacement source selector is added.

The existing installed-bundle observer also binds the actual called Qt getter
entry to the non-unloadable main Mach-O image and its original executable FD.
The existing complete IPA reader independently checks the selected artifact,
bundle bytes, header/UUID and executable file range. Device/inode/offset values
use canonical decimal strings across the unchanged JS/AFC path; other numbers
are bounded before V8 conversion. This establishes an entry-image/file-byte
association, not live instruction-page measurement or Qt SDK source provenance.

`IOSInstalledAdapter._chat_qml_cache_source(selector, run)` connects these
existing readers and InstalledCodeBinding using the already established SDK
session. Candidate/process/source continuity and the original journal must
agree before and after. A lost read raises without replay or returning an old
successful receipt. Its internal result keeps SDK-source, import and AOT
availability false and cannot admit a complete Chat capability.

The preceding Chat27 selection passes **45 host cases in 0.819 seconds**: thirty
cache/file/byte-binding and physical-adapter cases, three existing offline Qt
patch cases and twelve direct-v1/HTTP/AFC regressions. Real private application
and reverse-check cover nine Qt files plus two unchanged references. All5632
source/launcher/reference byte/stat/membership pins agree;161 test files remain
retained and the owned process group is absent. Log:
`.ios-host-tmp/chat-qml-cache-integration-20261028/root45-first.log`.
Qt, dyld, OS and SDK producers remain explicit models; the native code was not
compiled, linked, installed or run on a device.

Complete import/AOT and actual SDK source/build-ledger admission remain missing,
as do durable normal-input composition and the remaining Chat peer/outage/
restoration/resource/process/SDK retirement flow. The image-byte connection does
not close these boundaries. Feature10 remains partial; five of fourteen areas
are source-complete.

The later [dependency/evaluation connection](CHAT_QML_DEPENDENCIES.md) extends
the same readers to version three and binds both actual Qt getter entries to
one original IPA. Its 59-case host selection and immutable loader-DTO limits
are recorded separately; the preceding 45-case timings are not transferred.

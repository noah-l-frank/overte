# Partial original QML dependencies and evaluation transport

The existing Chat compiler/cache/file connection now transports Loaded-source
and outer Chat-source version three. Literal version-one and version-two
decoders remain unchanged. The same normal source request, Probe, private
writer, HTTP/AFC path and already bound SDK session are used; this adds no
normal input, selector, session, cache clearing or successful fallback.

The optional matching Qt6.11.1 patch captures actual resolved-type and script
edges at existing loader completion. Loader writers invalidate before mutation
and publish immutable diagnostic DTOs. The UI getter traverses atomic shared
pointers to those DTOs and weak diagnostic lifetime tokens, without traversing
mutable child Qt containers or acquiring product references. Revision, pointer
and lifetime checks bracket two complete graph passes. Destruction invalidates
the diagnostic token. Atomic shared-pointer operations are not claimed to be
lock-free. Compilation and native concurrency remain unverified.

Each node keeps original compiler/cache/code-owner generations, hashes and
loader capture clocks. Fresh graph-query clocks stay separate. Script events
require an actual unevaluated-to-evaluated module transition without a JS
exception; a cached value or already evaluated module cannot create an event.
An event remains historical and establishes no current parent/context
execution association. Repeated nonempty evaluation originals for one
ScriptData identity must agree; empty events and different historical child
edges remain permitted.

The [strict reader](adapters/chat_qml_cache_loaded.py) validates both graph
passes, reachable unique owners, original clocks, type/script slots, source
lineage, original event identity and bounded payloads. The existing owning
QObject/component observations still bind the current root. Loaded snapshots
retain their original load-time receipt and take separate current observations;
no older capture, compiler, write, mapping or evaluation clock is retimed.
Current dependency membership, current root evaluation, native type/dynamic
dependencies, imports, AOT and installed Qt SDK/source admission remain false.

`IOSInstalledAdapter._chat_qml_dependency_source` connects the existing reader
and physical adapter to both actual Qt getter function pointers. The existing
native image observer records each entry separately. The existing IPA reader
checks both observed offsets against one independently read original selected
artifact, executable range, header, UUID and bundle. Candidate/process/source
and journal guards run around the operation. Lost transport or binding failure
raises without replay or returning an older successful source.

The selected 59 host cases pass in 1.252 seconds: 45 preceding regression and
private patch cases, nine strict dependency/evaluation cases and five actual
existing physical-adapter/HTTP/AFC/IPA/JS model compositions. The second entry
at offset400 in an actual 512-byte modeled image with an executable range ending
at384 is independently refused. The same offline verifier applies/reverses the
13-file patch against 18 exact originals including five reference-only files;
unknown source and external scratch guards remain. All 5,687 source/launcher/
reference pins and 241 retained original files agree, with two post-stop
censuses, restored fixture aliases and no remaining owned processes.

These are host objects and explicit Qt/SDK/OS/dyld models. No Qt SDK patch was
applied to an installed SDK, compiled, linked or executed. Complete mutation
inventory, live child code-use/dependency membership, actual root/context
evaluation association, direct-literal graph transport, native type/dynamic/AOT
origins and independent SDK/build/source admission remain open. Durable normal
Chat composition and complete peer/outage/restoration/resource/process/SDK end
remain separate requirements. Chat remains partial; the count stays 5/14.

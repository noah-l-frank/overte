# Actual submitted Script code identity, version 1

This default-off E2E-only source identifies actual top-level code submitted to
ScriptEngine, independently of requested URL, bundled filename or platform.
It does not prove initialization succeeded, a timer fired, a module executed,
a pose changed, an installed binary is associated, or a device passed.

Immediately before the real `_engine->evaluate(_scriptContents, _fileNameString)`
call, ScriptManager records exactly that QString's UTF-16 code units in little
endian order, including unpaired units and BOM/newlines. It hashes those original
units with SHA-256. No file reread, fetch receipt, desired script or source URL
is used as the measured text. No input accepts a digest or code. The private
record retains original `submittedEpochMs`; later reads never retime it.

The existing mutex-protected RequiredModuleObservation owns the immutable
record. At most 4,194,304 code units (8 MiB encoded) are hashed once. Unexpected
second submission in the same manager, overflow or unavailable history makes
the observer unavailable. Before submission the original state is explicit
`submitted:false, codeUnits:0, sha256:"", submittedEpochMs:0`; it is not a source
identity. Empty actually submitted code has a real empty-content digest.
This capture changes no engine call, argument, execution result or product state.

The existing complete `feature-script-observe` source optionally adds
`sourceIdentityVersion:1`, and every manager row then has exactly
`code:{submitted,encoding:"utf-16le-code-units",codeUnits,sha256,submittedEpochMs}`.
Existing module/effect source contracts and wire schema stay 1. The source reads
copy original metadata; they never wait on a ScriptEngine heap or execute it.
The existing 128-engine/262144-byte and five-second/51-read transport limits
remain in force. Original source hashes/URLs stay in private test evidence.

`NativeScriptObservation.read(...,require_code_identity=True)` rejects older
sources. Once an identified source is observed, subsequent downgrade is refused
for that reader even without the flag. A submitted identity is immutable per
actual native manager ID; changed hash/unit count/time or reversion to pending
fails. A pending record may advance once to actual submission. Recreated
engines have their own IDs under the existing retirement rules.
`submitted_source` selects a unique active exact URL and requires submission;
its return value remains raw code provenance, not a function verdict.

The [Emote source pins](../feature_journeys/emote-source-pins.v1.json) record
reviewed source variants in their stated local parity bases. The profile helper
requires an explicit actually verified installed-resource scripts root, an
original validated code observation, exact active URL and hash/unit/encoding
match. A basename, label, platform or archive receipt cannot select a profile.
Unknown code, multiple active startup surfaces, duplicate managers and source
loss fail. The pins select input semantics only; actual panel lifetime, loaded
clips, advancing poses, images and independent peer observations are still
required. Pin regeneration is a reviewed source change, never runtime fallback.

The source review additionally reproduces an unresolved original tablet-script
boundary: non-Sit submits a numeric end frame; Sit submits `undefined` because
its local frameCount is assigned only in the other branch. The host check runs
the original JavaScript with explicit native boundaries. It proves that argument
fact only, not native conversion or physical Sit behavior. No replacement frame
count or functional fix is injected. This and the known chooser/override/Sit
semantic differences continue blocking a complete Emote producer.

The native code remains uncompiled. Twenty-five Script-source and seven profile
host cases cover old sources, immutable events, pending/malformed code, Unicode
unit identity, unknown hashes, installed-root isolation and ambiguous/retired
managers, alongside existing actual module/effect checks. Host simulations prove
reader/selector logic only. No full-area capability is activated. The canonical
iOS installed-code association block remains unchanged.

# Original consumed animation data, version 1

This E2E-only extension observes the bytes supplied to the actual FBX parser
and the original model subsequently copied/retargeted into an `AnimClip`.
It does not open a resource, reload a file, inject an animation, or accept an
expected filename/hash. Native instrumentation is uncompiled and all devices
remain unqualified. It enables no complete feature capability.

## Native acquisition and ownership

With `OVERTE_E2E_FEATURE_TESTS` and the existing `--testScript` admission,
`AnimationReader::run` records the actual `_data`, `_url` and returned non-null
`HFMModel` immediately after `FBXSerializer::read`, before normal publication.
The parser mode is taken from the actual mapping used by that invocation.
The registry holds weak model references, never a resource/model lifetime pin.
It prunes expired entries on publication and admits at most 1,024 live models;
capacity, invalid data or repeated publication of the same live model yields
no attributable source. No live original is evicted or retimed. Expired models
and reused pointer addresses cannot borrow another parse's identity.

The exact model record contains:

- `animationDataVersion:1`, random 32-lowercase-hex `instance` per parsed model;
- `sourceUrlSha256`, SHA-256 of the actual `QUrl::toString().toUtf8()`;
- `bytes` (1–33,554,432) and lowercase SHA-256 `sha256` of actual parser input;
- `parser`: `fbx-full-v1` or `fbx-skip-unused-curves-v1`;
- `frames` (1–1,000,000), `joints` (1–10,000) from that actual parsed model;
- `parsedEpochMs`, original positive native wall-clock time after parsing.

`Animation::featureSourceForModel` additionally requires the actual model owned
by that resource and adds `animationSourceVersion:1` and its own immutable
random `resourceInstance`. The real retarget operation obtains this record
from the same model reference it consumes. Each clip retains this original
record after normal release of its network resource and adds the original
`consumedEpochMs` and actual `blend` (`normal`, `add-absolute`, `add-relative`).
An empty animation cannot expose stale retained data. This metadata observes
ownership; it is not a readiness, decode correctness, pose or render verdict.

## Packet and strict reader

Each instrumented clip adds exactly `animationSourceVersion:1` and
`assetSource` (the exact resource/model record plus consumed time and blend,
or null when provenance is unavailable). Parse time must precede consumption,
which must precede the containing original snapshot and any nonzero original
clip evaluation time. Actual parsed frame count must equal copied clip frame
count. Unknown versions, numeric booleans, extra expected-result fields,
malformed identities and future timestamps fail validation. Legacy clips remain
readable as historical observations; they cannot qualify known file content.

The fixed [animation manifest](../feature_journeys/emote-animation-pins.v1.json)
pins the twelve existing FBX files at the common parity base
`7636452f2124029798948aafae70ecff5c5fa7d0`. `controlled` joins the actual loaded URL
and independently resolved observed name to original parser bytes, URL digest,
frame count, full parser and normal blend. A correct URL with another animation's
bytes fails. It returns original measured metadata, never a requested result.

Compiled Emote profiles require this join for every original advancing playback
sample and the current active clip. All must retain the same resource/model/
consumption identity. Completed clips must still prove their original content.
A cache hit may predate the input: its consumption timestamp is never rewritten
to make it look fresh. The original image bracket additionally requires an
unchanged actual consumed source across the image. Native freshness, original
call provenance, advancing poses and independently decoded pixels remain
separate requirements.

## Bounds, failure and cleanup

The reader inherits source-group freshness and owning Phone deadlines (1.5
seconds for fresh evidence, 5 seconds for one bounded owning acquisition); it
performs no transport, polling or implicit retry. Unknown/oversized/foreign
content fails the known-content join. No fallback hashes the requested URL or
rereads disk in place of consumed bytes. Passive cache readiness is a separate
required component; this record alone does not establish that every Emote can
start.

No additional timer, input, file, entity or network operation is created.
Metadata disappears with its original clip/model; weak registry entries are
pruned on later publications or process destruction. The enclosing owners must
still retain immutable observations, release their existing inputs/captures/
fixtures, and prove normal cleanup. Metadata absence cannot repair incomplete
cleanup or promote a failed observation.

Host tests hash real local fixture bytes independently of expected pins and
compare them to the immutable Git base. Their parser/model boundary is synthetic:
they do not parse FBX in the client or establish native compilation/product
behavior. Counterexamples cover wrong bytes at the right URL, missing/null/
foreign provenance, replaced/retimed identity, mixed image brackets and failed
scope retirement.

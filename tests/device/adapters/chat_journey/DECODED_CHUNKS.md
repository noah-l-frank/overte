# Original warm transcript decoding

The internal `chat-source-decoded-prefix` v1 prototype avoids repeated
base64/inflate/strict-JSON/canonical work for already admitted immutable source
transcripts. It supplies no native fact, current observation or owner. Cold,
return and archive loading keep the original complete decoder by default.
Persisted source-chunk v1 and publication v3 bytes and hashes are unchanged.

`ChatSourceChunks.load(manifest, decoder=...)` accepts only the exact bounded
candidate type. The original complete inventory, per-file signature before,
full `PrivateFeatureState.read`, signature after, exact child keys, version,
scope/index, canonical child SHA, complete raw-byte accounting and final
signature/inventory verification remain in their original order. The optional
candidate replaces only transcript `unpack`. Old entries must match the same
root path/scope, manifest prefix, all eight original file signature fields and
original decoded-byte SHA. New entries use the original complete `unpack`
and strict JSON-type admission. Outputs are new JSON inspection copies.

Admitted entries contain only exact immutable tuples, bytes, strings and
integers. A sealed tuple identity and its small metadata signature cannot
silently adopt replaced data. Every used decoded byte string is rehashed
after the full original physical file read. The warm cache never supplies a
new source epoch or replaces a current query.

The live Reader stages one candidate per original graph history. It commits
these only after the original complete source/phase/journal transaction,
actual outer lock exit and original freshness checks. A final unchanged
process/physical/cache/native-age guard follows admission. A separate decoder
checksum keeps cache commits from refreshing the unrelated general ownership
checksum. Late commit with frozen host time and advancing native time remains
a failure. Expected phase waiting cannot admit its uncommitted computation;
failed transactions remain failed, with their original journals retained.

Prototype measurement on seven actual retained histories used five complete
physical passes each: original loads totalled 0.684 s, cached decode 0.508 s
(about 0.137 to 0.102 s per seven-history pass). This is roughly 35 ms less
in the load component, not an established whole-run improvement. The complete
source/native/clock/quiet/cadence/120-second contracts remain unchanged.

After strengthening the pre-use/commit metadata checksum, the final historical
measurement used three complete passes over those same seven histories:
0.1307 s original versus 0.1045 s warm per complete pass. This is about 26 ms
(20% of loading, roughly 2% of the previously profiled whole source pair), not
a whole-run qualification. The benefit is deliberately reported at that
limited scale; no whole retry follows from this measurement alone.

Seven codec/identity/candidate cases and all 21 short Reader cases passed
together (28 cases in 32.028 s), including frozen-host/native-jump commit,
outer-lock-exit failure, unrelated ownership mutation, physical replacement,
cold v2/v3 compatibility and lost-part/ready-write cases. Twelve unchanged
default SourceChunk cases passed in 0.431 s. The first new warm-reader test
failed at a missing test-only `unpack` import; that import was corrected before
the complete green selection. No source guard or budget was relaxed.

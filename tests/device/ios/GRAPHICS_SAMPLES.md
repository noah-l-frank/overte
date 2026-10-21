# Original iOS Graphics role samples

`IOSGraphicsRuntime._graphics_samples` composes the existing canonical iOS
sources into `IOSGraphicsSamples`. This internal producer supplies no feature
capability or actor publication itself. The outer [Graphics owner and worker](GRAPHICS_FINALIZATION.md)
now implement the complete source-level journey and teardown.

Each run/role/process stage has its own version-3 private index (readers 1/2/3), independently
acquired native settings/scene/UI histories, fresh image nonce, image ownership
file, original PNG and immutable sample record. The index records responsibility
before the image owner can issue a native capture. Original source floors and
present immutable histories are restored; archived samples never satisfy a new
read. Source birth, PID, actual frame identity, sequence and original epochs must
advance or remain consistent as appropriate. Whole-candidate binding, role,
stage, fixture identity, image policy, original sample hash and private artifact
root cannot change on reconstruction. A ready index's cursors must match its
last immutable sample rather than an independently editable cursor cache.

Acquisition uses fresh native settings and subject v3, original generic Graphics
and tablet surveys, the original pre-HUD Vulkan PNG/chunks, actual native consumer
retirement and a second subject/settings read. A native/host clock acquisition
binds all originals; its 1500 ms ceiling also covers final sample persistence.
Original native epochs remain untouched and the public timestamp is the actual
host acquisition beginning. Requested settings do not replace actual allocation
ratios or marker/effect pixels. The tablet remains visible during image reading.

Each original PNG is retained after native retirement. Historical reading checks
the exact file/inode, original bytes/pixel hashes, chunk transcript, capture and
original retirement receipt. Later fresh absence queries can extend the native
owner's history without replacing the archived sample's original proof.
`drain()` independently observes actual native consumer/buffer/PNG absence for
every indexed image. It neither removes ownership metadata nor proves the final
three-second whole-run quiet window. A separate cleanup-only reconstruction can
drain an interrupted acquisition but cannot publish or reset it.

Version 2 adds explicit crossed-phase retirement records and preserves original
version-1 indexes/sample records without retiming. If a later actual fixture
phase interrupts a capture, `retire_crossed_phase()` separately observes that
phase, acquires current native clocks and proves the old capture's actual native
consumer absence. It retains the original frame metadata, partial/full file and
all command responsibility. Its record is explicitly abandoned and cannot be
read through the image-observation archive API. Its older capture timestamp is
excluded from the fresh retirement clock join. The role observation sequence
does not advance; only a different new original capture may publish afterward.
An unchanged phase or a changed native GPU birth cannot authorize this path.
An interrupted retirement stays durable and cannot be silently retried as a
product observation. Final whole-run file/metadata retirement still needs quiet.

The shared image verifier now classifies actual ambiguous/mismatching challenge
pixels with `MarkerNotReady`, selected from frozen Phone
`fe4684bf46585088370b3a328a738f147e670b97`. This remains an `AssertionError` and
the ordinary verifier still fails immediately. Only a completely retained,
native-retired and clock-qualified acquisition can be recorded as marker pending
and followed by a different owned original frame. Truncation, invalid sources,
uniform feature pixels and general assertion errors do not authorize that path.
An interrupted command, lost return, held native work or changed source remains
durable; reconstructing a producer cannot repeat the capture.

Seventeen sampler tests pass with real temporary private files and loopback fixture
responses, actual iOS HTTP/AFC UI framing and synthetic native/GPU SDK boundaries.
They cover separate reader credentials/role files, fresh originals after
reconstruction, a visible Graphics tablet, current-marker readiness, lost
capture, changed GPU birth, reused frames, altered files/sample records, failed
intent persistence and late acquisition. The initial ten-case sampler packet
passed in a 62-case selection with preference/history/scene, world measurement/
effect, byte-evidence and Vulkan owner regressions. Six unchanged shared Graphics
journey regressions also passed. The version-2 cases cover crossed-phase recovery with a new
capture, same-phase refusal, replaced GPU birth and unchanged version-1 original
archives during migration.

Remaining composition includes independently
credentialed actor publication, native WK marker-view/callback lifetime, final
quiet cleanup and the unchanged full fifteen-step iOS journey. A crossed fixture
phase retains acquisition responsibility and fails instead of publishing; the
outer live coordinator can now invoke the separately qualified crossed-phase
retirement path before a fresh capture. No native compilation or device qualification was
performed; physical transport/GPU timing is unmeasured and deadlines are intact.

`archive_index()` now validates retained old-process indexes, original records,
PNG bytes/chunks and retirement receipts entirely through private files and
pure original-source parsers. It performs no candidate/SDK/native admission and
cannot produce a usable live reader. The exact old index must remain owned and
locked. This permits restart recovery to inspect old evidence while the original
process is stopped, without querying a replacement source as if it were the old
one. Abandoned partial/empty files receive inode-ownership inspection only and
cannot become image evidence. Historical scopes reject read, drain and phase
retirement. A dangling foreign artifact is present, including when its target
does not exist; neither cleanup nor phase recovery treats it as absence.

The additional archive/partial-file/foreign-artifact packet passes 26 selected
sampler and shared Vulkan-owner no-build cases. The [restart controller](GRAPHICS_RESTART.md)
now independently drains live owners before stop and proves original PID death,
new native birth/counters and unchanged candidate before adopting sources.

## Retired fixture authority and sample writer version 3

`retire_inactive_run` can release an uncertain acquisition after the fixture has
actually closed, including when its last ticket is unchanged. A new read of the
existing immutable phase-authority source brackets the actual inactive Graphics
provider. Both sources must be retired with the same complete activation-ticket
history, and the controller acquisition remains bounded to 1500 ms. A missing
retired journal record or a merely inactive resource provider is insufficient.
This version-1 original is implemented in `graphics_run_retirement.py`; it grants
no product fact, published entry or native resource absence.

The sample still requires separately acquired actual native clocks and original
release receipts. No capture is replayed. Version-3 abandoned records use
`phase: null` plus the exact `runRetirement` original, keeping the original
capture ticket, retained partial file, native floors and history. A committed
record with a lost return is adopted unchanged after a fresh original authority
check; the native release/capture is not repeated. Such adoption is historical
ownership, not a new native absence sample. Whole cleanup still needs fresh
release/process and quiet-window proof.

Writers now emit sample/index version 3; versions 1 and 2 remain readable without
retiming or rewriting their original files. Older versions cannot contain the
new retired-authority abandonment form. The observer frame reader accepts all
three nested sample versions. Pure owned archives preserve abandonment as
abandonment after metadata removal. Whole observer/publication finalization and
paired final Stop/process retirement remain separate unfinished integration.

The combined retired-sample, existing sample, owned archive and independent
observer selection passes 54 no-build host cases in 186.795 seconds. The coupled
two-role whole-owner restart also passes separately with v3 samples. All five
selected project suites, registry and whitespace checks pass. Sources, pixels,
SDK/native and OS boundaries remain synthetic; no compilation/device result is
implied. A prior failed selection retained an obsolete migration assertion, and
another used the wrong expected exception type for the deliberately unavailable
journal transport. Both test expectations were corrected; neither failed run is
reported as a passing aggregate.

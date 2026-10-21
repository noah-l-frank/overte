# Phone owned original Emote image acquisition, header version 2

`PhoneEmoteCapture` connects actual guarded Phone avatar/model/world-render
factories, original PNG files and verified render-memory/receipt retirement.
It owns one image acquisition, performs no ordinary feature input and advertises
no complete Emote capability. Controlled world/avatar content, fresh selected-VM/
Rig/input causality, paired body pixels, actor publication, quiet-window and
whole-fixture/UI/run retirement still require the complete coordinator.

## Authority and closed durable record

Construct with a real `PhoneEmoteSources`, its held existing Script-source lock,
its actual run/role/candidate/process/session binding, an index 1–256 and the
closed world-render image policy. The source journal and immutable originals
are independently reopened through `PhoneEmoteSources.archive`, bracketed by
actual candidate/process guards. Substituted in-memory source state or a changed
source journal cannot authorize a capture. Historical replay makes no native
queries. Index is caller-owned bookkeeping; the full coordinator must persist
allocation and prevent reuse. Actual GPU acquisition/query sequences remain
independent measured fields. The native owner retains its global capture bound.

The exact private header is `emoteCaptureVersion:2`, `runId`, `fixtureUrl`, `role`,
`index`, actual `binding`, `artifactRoot`, `imagePolicy`, `parentScope`, compressed `payload`.
`parent_scope` is null for standalone captures, or the existing observation
owner's random 32-hex `scopeId`. The constructor validates and persists that
exact parent identity before acquisition. Historical readers preserve it; they
cannot join another attempt that happens to reuse the same phase/index/ticket.
Version 1 headers remain readable with null parent identity. The existing image,
cleanup and retirement archive schemas remain version 1.
The file is `phone-emote-<role>-capture-<index>.json`. Existing 64 KiB atomic/private
metadata limits remain unchanged; the maximum 128-model native table is covered
by a real host-file test. Primary/actor and different indices have separate
files; none establishes independent peer publication by itself.

Payload contains exactly one record with these fields:

| Field | Meaning |
| --- | --- |
| `phase` | `ready`, `reading` or `complete` |
| `providerBefore`, `providerAfter` | Original same-ticket fixture phase packets |
| `avatarBefore`, `avatarAfter` | Full original loaded-avatar/query metadata |
| `capture` | Full original GPU capture packet |
| `draws` | Full original same-PNG executed model table |
| `image` | Original planned/opened/saved Emote PNG ownership record |
| `captureIntent` | Exact original acquisition command, durably retained before dispatch |
| `retirement` | Actual memory plus complete issuer-receipt absence proof |
| `storage`, `inventory` | Latest original native retirement query cursors |

Initially all fields except `phase:ready` are null. A complete record requires
all originals, saved PNG and correlated retirement. Invalid/partial records are
never relabelled as complete. Failed writes latch the live object. Reconstruction
can validate a committed complete historical record after a lost return, but
cannot redeliver an uncertain acquisition or manufacture a fresh result.

## Acquisition and original verification

`read(ticket)` permits only a new scope and a ready source owner. The actual
existing role-specific render owner must be empty. It persists `reading` before
queries, verifies the current original fixture ticket, obtains a new avatar
observation, and joins its actual native birth/Rig to the independently retained
original source frame. Its factories must be real typed Phone readers and retain
the same PID and native-clock transport.

This journal first persists the exact acquisition command, then the existing
world-render owner persists the same command, and both are independently reopened
before original dispatch. A lost downstream ownership-write return therefore
leaves the exact known nonce available for ordinary verified retirement without
repeating the image request. A failed first write never enters the downstream
owner; a missing owner without actual retirement proof remains unresolved.
Neither journal may recreate or adopt a foreign owner. The completed original PNG, separately queried
same-capture model table and later avatar observation are durably retained.
The existing file engine persists legal planned→opened→saved PNG transitions.
No expected source, pose, image, bounds, feature state or desired result enters
native requests.

Cleanup of measurement resources precedes `complete`: native storage release,
separate actual zero-buffer/zero-callback inspection, complete original issuer
inventory removal and a separate actual receipt-file absence query. The complete
proof is validated and persisted **before** the native ownership journal is
discarded. The old storage/inventory cursors survive cleanup reconstruction.
An ACK or missing host journal alone cannot establish release. Reconstructed
cleanup cannot adopt a foreign capture or forget an unknown delivered request.

A final original phase must retain the same actual ticket. The original PNG/
avatar/model/view/challenge/subject join is recomputed before publication.
All work, callbacks, writes, decoding, copies and guards consume the five-second
operation bound. Current native and provider freshness is independently bounded
to 1.5 seconds with host monotonic age floors, including a final decode/copy
under frozen external clocks. A late failure may leave a complete **historical**
record, but `read` returns no fresh observation in that case.

## Historical originals and safe scope cleanup

`original()` reopens the exact private PNG and verifies the committed native
record, phase/challenge, original image digest/pixels, inode and binding. It
returns historical `{ticket,avatarBefore,avatarAfter,capture,draws}` plus original
PNG bytes. It makes no native query, retimes nothing and does not supply a fresh
feature verdict. It cannot replay `read` in that scope.

`PhoneEmoteCapture.archive(header, source, index, policy)` validates a complete
historical child header previously retained by its parent. It reopens the same
actual PNG inode and bytes, validates every original capture/model/avatar/phase/
retirement join and returns `(frame, png, decoded_state)`. It requires the real
role-specific source owner, held lock, candidate guard and five-second local
bound. It deliberately permits later source-header advancement or already
retired child metadata. It supplies no fresh observation, adopts no missing
child and invokes no target query. The [observation owner](EMOTE_OBSERVATION.md)
commits that exact header to its immutable original file before child cleanup.

`cleanup()` retires only this correlated capture. Its five-second bound and
actual candidate/process guards also apply. It can finish retained native
buffer/receipt work, including after ignored release or missing callback drain.
Already retired scopes need their complete original retirement proof. A
delivered capture with a missing native ownership journal and no proof remains
unavailable; an empty list or remembered ACK cannot replace that authority.

Saved PNGs must still match their actual file identity and digests. A planned
file must be independently absent; a preexisting foreign file is neither adopted
nor deleted. An opened partial file must still be the actual private recorded
inode. It can remain retained failed diagnostic evidence, never decoded or
published as a valid image. Missing/replaced evidence prevents scope retirement.
Other native captures, source journals and retained evidence files are untouched.

The cleanup record is exactly `emoteCaptureCleanupVersion:1`,
`completeImageRecord`, original `retirement` or null, `retainedPartialImage`.
`completeImageRecord` means committed historical metadata, **not** fresh image,
Emote function success or whole-run acceptance. Only after original scope checks
does cleanup remove its exact host journal. General Phone cleanup attempts its
existing base teardown but refuses success while any matching capture journal
remains, including an unrecognized role/index filename. The full feature owner
must perform this component's cleanup before base teardown removes proof sources.

An interrupted parent source read may permit retirement of an existing child
scope with matching original binding; it cannot create/replay a new capture or
clear the parent's pending responsibility. If the app is backgrounded, its
ordinary lifecycle owner must first establish the authorized foreground cleanup
scope. This component performs no background activation, repair or restart.

## Parent retention before child metadata removal

`cleanup(retain=callback)` adds a bounded parent transfer. The callback receives
an exact `emoteCaptureRetirementVersion:1` record with `sourceHeader` (the original
source journal/immutable-file references), `header` (the exact updated child
journal including original native buffer/callback/issuer-file proof), `cleanup`
(the existing v1 cleanup result), and `partialFile` (null or actual diagnostic
metadata). The callback must durably retain the exact private record before
returning. Returning false, throwing, losing the candidate guard, exceeding the
five-second operation budget, changing headers or introducing another render
owner prevents child metadata removal. The child originals are reopened both
before and after parent retention IO. Missing/replaced source/PNG files remain
errors. The enclosing feature owner must use this callback when transferring
responsibility; the legacy callback-free component API alone establishes no
parent retention or full-run cleanup.

A partial image has exactly `name`, original `file:{device,inode}`, measured
`bytes` and measured lowercase `sha256`. These come from the actual owned
incomplete private file, including a possible empty file. Its expected full PNG
digest/length is never returned as measured diagnostic data. Planned files must
remain absent; foreign files are neither adopted nor removed. Partial files stay
retained and are never decoded/published as valid images.

`PhoneEmoteCapture.retirement_archive(record,source,index,policy)` independently
reopens the retained original source files and owned image/diagnostic bytes,
validates exact role/run/candidate/process/native birth and historical cleanup
proof, and returns the original record. It works after child metadata removal
and issues no target query. Original model/capture proof and measured partial
bytes must remain unchanged. Failed captures remain failed, including lost GPU
returns, even if their native resources were safely retired. This historical
record is not a new memory inventory, fresh image or whole-feature verdict;
the full coordinator must still prove its final quiet window and resource
absence, preserve failure status, recover interrupted parent scopes and retire
all other run ownership.

Nineteen acquisition host cases plus a general-cleanup counterexample exercise
actual Python readers, private source/PNG/metadata files and real render owner/
receipt logic against synthetic native boundaries. They cover lost results,
ignored buffers/callbacks/receipt removal, foreign sources/draws/markers/files,
interrupted writes/source reads, missing ownership/evidence, final staleness,
role/index separation and the maximum model table. These verify test logic only.
Native code remains uncompiled and all devices untested; full Phone areas remain
three of fourteen.

# Phone current Emote input, Rig and image observation, version 1

`PhoneEmoteObservation` composes real source/input/effect readers, the existing
owned GPU capture and original PNG/body-pixel verifier. Each role acquires its
own current sources and PNG. Primary input receipts establish causal barriers
only; actor facts never forward primary measurements. This internal component
advertises no complete feature capability. Approved domain/Script membership,
scene/view ownership, background recovery, authenticated actor publication and
whole-run cleanup remain the enclosing feature owner's responsibilities.
The [v2 source selector](../../native/EMOTE_SOURCE_PROFILE.md) now admits normal
Phone Emote inclusion inside the default-script manager using original compiled
source and caller identities. [Lifetime v2](EMOTE_LIFETIME.md) now joins scoped
timer/callback work in that shared VM. Whole admission, recovery, actor publication
and run retirement remain open before complete feature registration.

## Authority and operations

Construct `PhoneEmoteObservation(effects, index, image_policy)` with a real
`PhoneEmoteEffects` v2, its held source lock and acquisition index 1–256. Role,
run, actual candidate/session/process binding, fixture root and private artifact
directory come from the real source owner. The image policy has exactly
`source:world-render-target`, `marker` and `subject`; the existing projected-body
and marker contracts apply without relaxed image or metadata limits.

`read(ticket, played=None, previous=None)` performs one new observation. Its
current acknowledged ordinary input must have this exact actual fixture ticket.
`played` is the existing role-local original playback reference needed for later
restoration. `previous` is an earlier real completed observation in the same
role/run/candidate/artifact directory and with the same image policy. It supplies
only the independently reopened historical PNG for changed-body comparison.
No expected name, pose, pixel statistics or success flag enters a native query.

The sequence is:

1. Persist observation responsibility before any new source/image acquisition.
2. Read one new role-local source group and check the original consumed-input
   barrier. Retain the exact original pre-image frame reference.
3. Acquire the actual PNG/model/avatar originals. Capture itself proves actual
   native buffer/callback and issuer-receipt retirement.
4. Commit the exact complete child header and pre-image reference to an exclusive
   immutable parent original file **before** removing the child scope or advancing
   the source header. A failed parent write leaves the child and pending file.
5. Retire the child metadata and retain its exact original cleanup proof.
6. Obtain one new role-local source group after the image, recompute current
   actual input/Rig effects, and independently read actual loaded avatar resource
   configuration. Both bundled resources must match the existing repository byte
   pins and exact original Model/Geometry/Rig/raw-source identities.
7. Join the image to that stable native interval, measure original current/previous
   pixels, commit the original outcome and validate final freshness before delivery.

Native pre-image capture must precede the image's first avatar request. The
image's last avatar capture must precede the post-image configured-root request.
PID/native birth/Rig agree. Actual lifecycle counters, animation history instance,
call cursor, override generation and active state remain identical across the
interval. Active clips must already be loaded before image capture, with the same
actual resource/range/rate/loop/loaded-frame count afterwards. Instrumented clips
must also preserve their exact original consumed resource/model/FBX identity
across the image; compiled Emote playback checks the fixed actual-byte pins.
A restore, restart
of the same clip, different override or background during capture fails. A later
correct Rig sample cannot retroactively qualify an unrelated image.

The native playback proof still requires at least two original advancing loaded
frames with changed final poses; the fresh pre-image and post-image acquisitions
can provide those frames. Removing duplicate acquisitions does not permit a
call-only, frozen pose/clip or stale image proof. This halves source groups per
new image. It does not by itself solve the complete run budget: the shared
runner requires at least three fresh samples per checkpoint, and up to 169
ordinary actions. Full coordination must retain and transfer bounded archive
segments and original comparison images without dropping unresolved ownership;
existing per-owner limits are unchanged.

The Phone-only uncached private command reader is now polled before the probe's
250 ms heavy-sample throttle, at most once per 20 ms of advancing wall time.
The fixed debug marker must already be admitted; initial admission still occurs
in the ordinary sample. Sample-side reads share the same poll cursor, so one
update cannot read twice. A backwards clock rebases without dispatch. Missing
Phone hooks retain the existing sampled Android channel. Native command parsing,
operation nonce guards, source freshness limits and observation requirements are
unchanged. This removes a source-imposed 250 ms delay for each sequential Phone
command; it is not a measured transport latency or device performance result.
The whole-run owner must still meet the actual freshness and timeout budgets.

Pixel verification independently checks the actual original model draw, projection,
challenge, PNG/pixel hashes and role-local comparison. A changing challenge with
a frozen body, changing background/camera, foreign image or missing original
remains unavailable even when the loaded animation is correct.

## Exact private records

Each scope uses `phone-emote-<role>-observation-<index>.json`. Its outer fields are
exactly `emoteObservationVersion:1`, `runId`, `fixtureUrl`, `role`, `index`, actual
`binding`, `artifactRoot`, `imagePolicy`, and the existing packed `payload`.
Decoded state has exactly:

| Field | Meaning |
| --- | --- |
| `phase` | `reserved`, `capturing`, `captured`, `measuring` or `complete` |
| `ticket` | Actual current ticket, initially null |
| `capture`, `outcome` | Saved compact immutable-original references or null |
| `pending` | Null or exact `{kind,original}` planned/opened/saved responsibility |
| `retirement` | Actual child cleanup proof or null |

`ObservationOriginals` reuses the existing private exclusive/inode/digest file
engine with closed kind `observations`. Existing source/input readers still
reject this kind. Each scope reserves indices `2*(index-1)+1` for its capture
original and `2*(index-1)+2` for its outcome, within existing 1,024-record bounds.
There is no parallel journal engine or increased file/metadata limit.

The capture original has exactly `emoteObservationFrameVersion:1`,
`kind:capture`, `ticket`, role-local `before` source reference, exact child
`header`, original `played` reference or null, and `previous` or null. Previous
is exactly `{index,capture}` pointing to the earlier same-role capture original.
The outcome has exactly `emoteObservationFrameVersion:1`, `kind:outcome`,
`ticket`, role-local `after` source reference, original native `configuration`,
original measured `effect` v2 and measured `pixels` v1.

The private returned record has exactly `emoteObservationResultVersion:1`,
`role`, `index`, `runId`, `binding`, `ticket`, actual `state`, original `effect`,
recomputed `pixels`, exact retained child `image` header and immutable `capture`
and `outcome` references. It contains private source/context data and is not a
public journey result or peer receipt. The future owner must use the existing
public projection, alias, privacy and authenticated actor contracts.

## Freshness, interruptions and retirement

The combined operation has a five-second monotonic bound. The earliest original
pre-image source and fixture observation must remain within 1.5 seconds at final
delivery, including image IO, archival validation, native configuration, pixel
comparison, final provider/guard work and copies. Host/device epochs are separate;
whole-operation monotonic floors detect frozen external clocks. A late delivery
may leave complete historical evidence but cannot return fresh success.

`original()` reopens immutable parent records and the original PNG, rejoins native
image brackets and actual resource pins, recomputes the full input/Rig effect
from original input-history prefixes, and recomputes pixel statistics from
original bytes. It is historical only, sends no target query/input and never
refreshes timestamps. Later source-header advancement does not erase or refresh
that evidence. Missing, equal-byte replaced-inode or corrupted files fail.

`retire(retain)` requires a complete original result, original child retirement
proof and absent child scope. The mandatory callback must durably retain the
exact private proof before returning. A failed callback, changed candidate or
five-second retention timeout preserves observation responsibility. Original PNG
and immutable evidence files remain retained. This retires one measurement scope;
it is not a whole-feature cleanup verdict.

Interrupted scopes cannot replay acquisition or become complete through missing
metadata. A lost child-cleanup return preserves the parent's original capture
but supplies no outcome or successful observation. The bounded incomplete-parent
transfer below can retire that measurement scope's metadata while preserving the
failed phase and every original. Earlier or partial acquisitions
remain explicit unresolved responsibilities for enclosing failure recovery;
general teardown rejects any remaining observation filename, including unknown
roles/indices. The enclosing coordinator must implement that recovery before a
complete Emote capability can be enabled. No timer clear, native pose setter,
fixture repair, input replay or product-function change is introduced.

Host cases exercise the real Python acquisition, filesystem and measurement
logic against synthetic native/SDK/Qt/GPU boundaries. These verify test logic
only. Native code is uncompiled; devices remain untested. Complete Phone feature
adapters remain three of fourteen.

## Incomplete original archive transfer, version 1

`transfer_incomplete(retain)` is restricted to existing `captured` or `measuring`
parents with a saved complete child image original and no pending parent-file
write. It acquires no new image, source, native observation or ordinary input.
The complete immutable child must already contain original independently
observed memory/callback/issuer-file retirement. A missing child file alone
cannot supply that proof. The actual same-role world owner must currently be
absent; a foreign/current owner is neither adopted nor released by this path.
If the exact complete child metadata still exists, ordinary child cleanup
revalidates/removes it while the durable parent capture original remains held.
If a child cleanup return was lost, the parent can recover only the original
subresource-retirement field from that already committed proof, after reopening
the full original capture/PNG and checking the current world-owner absence.

The mandatory retention callback receives exactly
`{emoteObservationIncompleteArchiveVersion:1,header,inputHeader,inputSourceHeader,sourceHeader}`.
There is no returned result, derived product state or fresh-observation verdict.
The original incomplete phase remains unchanged. Primary/actor archive contexts
retain separate original sources; a post-image source journal may still contain
an interrupted read. That source/input journal stays owned and unresolved.
If an outcome was fully committed before its final complete-phase write failed,
its full input/Rig/image/pixel facts are recomputed without promoting the phase.

The existing five-second whole-operation bound includes the initial candidate
guard, original-file replay, child cleanup, callback IO, a second independent
replay and final guards/copies. The exact source/input headers must stay unchanged
across retention. A rejected/slow callback, new child/world ownership, missing
or replaced PNG, changed original/context or uncertain retirement write prevents
parent metadata removal. A failed live write requires reconstruction; no
acquisition or product input is repeated. Immutable files and PNGs remain held.
`incomplete_archive(packet,effects,index,policy)` reopens the retained exact
contexts and originals after metadata transfer, with no live native getters or
timestamp refresh. Historical views cannot perform live source/input operations.

This transfers one incomplete measurement's responsibility. It does not retire
the whole failed run or prove current global native/resource absence. The final
owner still needs fresh native quiet/absence, actual fixture/UI/scene/view/actor
cleanup and all host-journal retirement. A parent without a saved complete image,
or with an opened/planned/pending parent original, remains red and cannot use
this narrower recovery path. Complete feature registration remains disabled.

## Complete original archive transfer, version 1

`transfer(retain)` supplies the full parent with the exact
`emoteObservationArchiveVersion:1` record: `header` (this scope), `inputHeader`
(primary input owner), `inputSourceHeader` (its original source journal),
`sourceHeader` (this role's original source journal), and recomputed `result`.
Primary source headers must be identical; actor headers remain independent.
Every header retains its original immutable-file references and binding.
The callback must durably retain the exact private record before scope metadata
is removed. The existing five-second bound includes context replay, copies,
callback IO, a second independent archive check and final guards. Changed source/
input journals, lost candidate authority, incomplete capture retirement, new
child metadata or missing originals prevent transfer. Original files and PNGs
remain retained. This transfers metadata responsibility, not product cleanup.

`PhoneEmoteObservation.archive(record,effects,index,policy)` rebuilds private
historical source/input views from those exact retained headers, reopens the
original files, recomputes input/Rig effects and image statistics, and compares
the entire returned result. It works after live metadata has advanced or been
transferred. The supplied actual effects owner provides current role/run/
candidate/process/artifact-root/lock authority; it supplies no replacement facts.
Archive views explicitly reject live source reads/writes, inputs, captures and
fresh effect operations. No fake live metadata store is introduced. Historical
replay sends no native observation command, fixture request or input and never
retimes a result. Candidate guards and the replay deadline remain mandatory.

`read(previous=...)` also accepts one complete archive record of an earlier
same-role checkpoint, besides the original live-scope form. It first replays that
complete record, then retains its original capture reference for pixel
comparison. Wrong roles/contexts, uncompleted records, missing files and a
non-earlier index fail. Three fresh stability captures may reuse the same current
phase index after each successful transfer, while all compare against the same
earlier completed checkpoint. Actual request nonces make PNGs unique; original
content hashes/inodes distinguish retained capture/outcome files even when their
bounded logical indices repeat. No input or image is replayed and no index/file
limit is increased.

The full coordinator should use an actual fixture activation sequence for the
bounded phase index, rather than treating it as a global count of every poll.
It must still own and validate source/input metadata handoffs between bounded
segments, link original native/Script/UI continuity across those segments,
preserve every archive and failed responsibility, and establish final cleanup.
These remaining joins are required before complete Emote registration. The
legacy `retire(retain)` returns/retains only the result and cannot by itself
supply this full reconstruction context.

Host cases verify independent primary/actor replay after live metadata removal,
blocked live operations on historical views, changed context/results and missing
originals, failed/slow retention and three actual new capture IDs in one phase
without additional product inputs. These are source/logic checks only. Native
compilation and device qualification remain pending.

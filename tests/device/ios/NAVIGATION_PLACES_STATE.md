# Original Places, bookmark and Go To field projection

`navigation_places_state.compose` joins six actual fields: bookmark presence,
owned bookmark name, search query, owned search-result IDs, Places panel and
Go To visibility. It deliberately returns private `fields`, not a complete
Worlds state. Actual arrival/rendered location, matching native missing-place
error, independent actor publication, durable whole-run ownership, restart and
resource cleanup remain required. No full capability is added.

The caller supplies the installed binding, attached original navigation-provider
inputs, original bookmark baseline, and original `bookmarks`, `model`, `ui` and
`http` packets. A `NativeClockAcquisition` must bracket these unchanged packets.
The existing clock join hashes all originals and the original UI sample time;
this component additionally checks every nested native read bracket against
the same native before/after interval and process. Native lifecycle counts must
remain unchanged. The inherited acquisition deadline is strictly below 1.5 host
monotonic seconds. Host UTC and filesystem times never refresh native packets.
Historical composition alone cannot claim a new live read or source cursor.

The bookmark baseline preserves its original installed/process binding, loaded
map, load-error bit and original file bytes/hash/inode/status. Admission requires
the loaded and persisted maps to agree, bounded string entries, and no preexisting
run-owned name. Each current read again requires loaded/persisted agreement,
preserves all unowned keys and values exactly, and allows at most one owned name.
An owned address must be actual controlled A. An absent empty file and an existing
empty JSON object remain different originals: ordinary deletion of the last
bookmark can leave `{}`. The component never deletes that container, invents
physical absence, or declares byte-for-byte file restoration from map equality.
Same-process bookmark source birth/counter continuity is checked against the
baseline. A replacement process must still be admitted by the whole restart
owner; candidate/target comparison here does not prove an authorized restart.

The current complete model must be version 2, agree with actual tablet visibility
and have no retained root loading, queued command, dispatch timer or visible
bookmark/rating/location popup. The actual active selected root must join the
original normal-input Places page UUID/source. Actual original search-field text
must agree across the model and control sources. Only bounded run-owned public
queries are projected. Results come from actual materialized rows, retaining an
incorrect product filtering outcome for the shared checkpoint to reject. Python
does not implement the filter or substitute expected rows. Closed Places projects
empty query/results while retaining hidden original roots and text privately.

The open bookmark tab retains its actual native QML search buffer and directory
model. Those unchanged model fields still supply query/results while the search
editor has no input token. The directory tab requires matching visible editor
text; both tabs require their actual list visibility to agree with the selected
tab. An incorrect retained filtering result stays visible to the checkpoint.

The first normal directory refresh creates an
`iosNavigationDirectoryProofVersion: 1` record through `directory_proof`. Its
original server body receipt, native actual text-read/callback and materialized
QML row are joined by `places_http.consumed`, including the response-specific
description marker and original input barriers. The proof freezes originals,
admission and derived materialization; reconstruction revalidates all of them.
Its configured source revision must match the installed binding.

A later fresh current page may retain that same genuinely fetched record. The
original proof's native read time remains old; it is never moved to the later
phase. Current HTTP history must preserve its original immutable prefix and
source birth/counter, and the model observer must preserve its original birth
and advancing read bracket. The current original record must equal the genuine
materialization, and any visible owned row must equal that original row. Native
origin/protocol and actual maturity filtering must agree. A newly delivered
response cannot lend its marker to an old model. A closed-page bookmark read
does not require a new directory fetch, which permits independent persistence
observations before reopening Places after restart.

Version 1 of the field projection retains binding, run, hashes of current
originals/baseline/optional directory proof, original native interval and the
measured host acquisition start. It does not journal cross-sample source cursors,
declare three-second stability, prove native/XHR/Web/GPU object absence, or
retire any metadata. The final owner must retain these originals and enforce
input, per-role/process, image, actor and repeated-cleanup responsibilities.

Host tests use real temporary bookmark bytes, the navigation input provider and
the unchanged Places JavaScript/QML processing/filter functions in Node. Native
Qt/UI/SDK clocks and observations are modeled. Counterexamples include ignored
typing, wrong filtering, missing disk writes, wrong addresses, dual owned names,
unowned edits, stale response markers, changed source births, hidden queues,
incomplete inventories, private queries, foreign process/candidate and bad clock
joins. Native compilation and physical device behavior remain unverified.

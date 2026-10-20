# Durable Phone Graphics original samples v2

`PhoneGraphicsSamples` joins the existing original sources with a private
role/process ledger and original PNG artifacts. It performs no normal product
input, fixture activation, app launch or SDK repair. This is an internal source
component, without a complete `feature.graphics.*` triple or advertised capability.
Native instrumentation is uncompiled and all physical clients remain untested.

## Scope and required sources

The constructor requires the existing credentialed Graphics `Client`, pinned
provider instance, run, role `primary|actor`, explicit process stage `0|1`,
canonical private artifact root, external world-target image policy and the
already-held `phone-script-sources.lock`. Both roles use read-only factories
bound to the actual installed candidate, existing SDK session and process.
The separate ledger is `phone-graphics-<role>-<stage>-samples.json`.

The acquisition order is original native preferences/lifecycle, actual subject/
view, original Graphics UI, original Tablet inventory, a new world-target GPU
frame/PNG, a second actual subject/view, a second native sample, and fresh
controlled-provider metadata. The pure [measurement join](GRAPHICS_MEASUREMENTS.md)
requires original ordering, native birth, steady pose/entities/settings, the
same actual recorded frame view and a current independently decoded challenge.
No desired setting or requested effect enters the source producer.

Every accepted original is saved before acquiring another. Source-owned native
lifecycle/account/voice/animation prefixes, UI generation/input/source counters,
subject history, GPU acquisition/sequence/birth, all seen frame IDs and native
storage/receipt cursors survive factory recreation. Every accepted memory query,
including nonterminal callback-drain observations, is durable before the next
request. Chunk cursors retain original metadata and an actual decoded-chunk hash
without embedding base64 PNG payloads in the journal. Complete PNG byte/pixel
hashes still require the original image. Cached originals restore
validation floors only. Every `read(ticket,after_epoch)` must acquire a new frame.
The whole source attempt is bounded at 20 seconds and retains each underlying
source's existing deadline. Original clocks are never retimed. Final native
clock and guard latency remain inside the 1,500 ms freshness requirement.
An independent local elapsed-age floor from the first original native acquisition
also prevents a frozen native clock from hiding slow PNG completion or cleanup.

## Files and measurement retirement

Before reading any native source, a pre-existing world-image owner is refused.
This sampler cannot adopt or clean another request. Its own capture nonce is
additionally saved after native ownership intent and before actual dispatch.
Even a lost dispatch response therefore has an exact durable cleanup correlation.

The original PNG uses [planned/opened/saved file intent](GRAPHICS_IMAGES.md),
exclusive creation and original byte/pixel hashes plus file identity. Every
intent phase is part of the sample ledger. Files are retained as private evidence.
No overwrite, arbitrary deletion or old-image retiming is provided.

The producer's `finally` path retires only its correlated native measurement,
using original memory/callback absence, complete native-issued receipt removal
and a separately issued complete filesystem absence query. Original memory,
both file results and exact role-bound ownership are retained in the sample.
A complete original retirement proof is durable before world-owner journal
discard; actual journal absence is checked separately. Lost or ignored discard
responses cannot lose the proof or turn remaining ownership green.
A release/remove ACK alone cannot complete it. All measurement ownership must
be gone before a ready sample can be returned. Changed birth/owner, outstanding
callbacks, ignored removal, incomplete rows or leftover files retain a red attempt.

## Interruption and archives

A pending attempt stays `reading`, including its original cursors, capture nonce,
partial image intent and any measured native retirement. Constructing a new
producer refuses that journal. It cannot reset provenance or return prior facts.
`retire_changed_ticket()` is available only on the live interrupted producer.
Reconstruction still refuses a pending journal. A fresh original active phase
must have another ticket, the right run/area and valid common arguments. The
controlled provider independently confirms the same current phase, with its
original append-only history; a second phase read must remain unchanged.

The method may retry measurement retirement only for the durably correlated
capture, original GPU birth, original process/role and retained source cursors.
Ignored cleanup cannot reset a previously accepted nonterminal source cursor.
It does not replay the GPU capture or any normal UI input. An unknown/missing
original capture remains red, even when the current files look empty.

A planned host PNG may retire only with actual scoped filesystem absence. That
original negative artifact is durable before dropping it from the pending image
list, including a lost phase-confirmation response. A known opened file must
independently match its original full PNG and inode before being recorded as a
saved historical artifact. Empty/partial/replaced files stay unresolved. Saved
files remain original historical evidence, without being relabelled current.

Successful changed-ticket retirement retains the original cursors, native
memory/file proofs, abandoned-file absence and both phase/provider observations.
It returns scope/history data, never measured feature state. The next `read`
still requires entirely new original sources/frame/PNG. Retirements are bounded
at 32 and the ledger/capture sequence at 256, with a 20-second total attempt
budget. Version 1 journals are refused without implicit upgrade or provenance
reset; `phone-graphics-samples` now reads only version 2.

`archive(...)` validates historical originals and every retained original PNG
without an adapter, SDK, native input, session repair or new current result.
It preserves original clocks and rejects missing/replaced files, late files at
an explicitly abandoned planned path, and borrowed
native/context/role/owner/absence proofs. Restart handoff and final run retirement
remain responsibilities of the future complete Graphics coordinator.

General Phone cleanup reaches base teardown and then refuses either role's stage
0/1 sample journal. The complete owner must explicitly verify and retire these
records; stopping the app cannot make unresolved source ownership green.

## Host verification

Thirty source cases, including loops over every source cursor and native/UI
birth, use real private host journals/PNG/receipt files with explicit synthetic
native and fixture boundaries. They cover original joins, factory recreation,
GPU-frame reuse, foreign/old pixels, lost dispatch and file-intent responses,
ignored native/file cleanup, pre-existing foreign ownership, wrong binding/
scope/policy, historical archives, unchanged/foreign/moving phases, original
changed-ticket recovery, unissued planned-file absence, partial images, durable
lost-confirmation recovery, lost/ignored owner discard, v1 refusal and bounded failure. A Phone wrapper case checks
general cleanup across both roles and both process stages. These tests qualify
test logic only; they are not native compilation or physical acceptance.

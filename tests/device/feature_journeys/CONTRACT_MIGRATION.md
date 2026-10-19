# Common feature journey migration: current version 3

## Version 2 to 3: actual recorded preview

Version 3 replaces the draft manual Audio Save/Preview/Stop transaction with
normal automatic three-second in-memory capture/play/drain/completion. It adds
actual phase/history, played-frame and live-buffer observations, rejects
impossible combinations and requires a whole completed native cycle with equal
captured/played frames and empty product buffers. A muted Start and mute or
background cancellation are tested through real user controls/lifecycle.
The existing composed `permission-recovery` foundation retains OS permission
checks; these are not replaced by an invented preview permission dialog.

`await-completion` is a bounded observation wait, not a new product control.
There is no client Save, Preview Start/Stop or Discard input on this surface.
The `file` evidence is lossless original input PCM acquired through dedicated
E2E instrumentation, not a user-exported recording. Independent acoustic PCM
must prove actual output separately; accepted native writes alone do not do so.
Both carry the three-second `recorded-preview-v1` challenge from that Start,
with actual native cycle/original event/byte provenance. Old source times must
not be relabelled as new recordings. The old `voice-v1` fixture is unchanged.

Current requests, observations, engine, registry, generated inventory and matrix
use `contractVersion:3`; observation `schemaVersion` and the independent
`/feature-fixture/v1` resource/journal transport stay unchanged. No qualified
version 1 or 2 complete platform producer existed. Prior requests/observations
are rejected; current files are `adapter-contract.v3.json`, `coverage.v3.json`.
Native Script/preview primitive contracts and the narrower foundations remain
independently versioned and unchanged. All devices remain untested.

Cleanup must close owned UI, observe inactive/empty native buffers, release and
separately observe absence of owned E2E evidence, and restore the original mute
state. Because the real native status retains its terminal history, restoring
an initial idle/history-empty baseline requires a real verified application
restart and new native context, not an instrumentation reset of product state.
This restart handoff and the normal Audio input/independent actor joins are
still required in the complete platform adapters.

The existing Graphics and platform Emote source mismatches still block those
area producers. This migration does not activate any full feature capability.

## Historical version 1 to 2: Script import

Version 2 corrected the Scripts user flow exposed by source review. Client URL
and file loads do not have the entity-script consent transaction assumed by
the original version 1 draft. That shared engine, strict contract,
generated inventory, coverage matrix and capability descriptions used 2 at that stage.
Observation `schemaVersion` stayed 1; `contractVersion` was 2. The existing
resource/journal transport `/feature-fixture/v1` is independently versioned and
unchanged. Existing foundation operation contracts are unchanged.

There were no qualified version 1 product producers on Phone, Pico or iOS.
Version 1 host simulations are historical logic checks, not producers or
accepted product evidence. No deployed producer/acceptance migration is needed;
that registry read only 2 and rejected version 1; the current registry now
reads only 3.
The old inventory and implementation remain recoverable in Git history; the
version 2 files remain available in Git history.

The Scripts state replaces `consent` with the observed `picker` flag and adds
`companions`, the relative modules actually resolved by the active owned
engine. Inputs are ordinary picker open/cancel/accept with the two owned local
source choices; a missing source is tested through normal URL entry. A running
engine or downloaded main file without advancing entity effects and actual
relative dependency resolution cannot pass. Entity-script consent remains in
the existing `scripted-entity` foundation.

Version 2 did not activate a platform adapter. Its remaining Audio assumptions
were corrected in version 3 above. Graphics and platform Emotes still need
source-compatible contracts and full input/observer joins.

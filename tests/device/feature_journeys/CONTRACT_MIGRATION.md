# Common feature journey migration: 1 to 2

Version 2 corrects the Scripts user flow exposed by source review. Client URL
and file loads do not have the entity-script consent transaction assumed by
the original version 1 draft. The current shared engine, strict contract,
generated inventory, coverage matrix and capability descriptions now use 2.
Observation `schemaVersion` stays 1; `contractVersion` is 2. The existing
resource/journal transport `/feature-fixture/v1` is independently versioned and
unchanged. Existing foundation operation contracts are unchanged.

There were no qualified version 1 product producers on Phone, Pico or iOS.
Version 1 host simulations are historical logic checks, not producers or
accepted product evidence. No deployed producer/acceptance migration is needed;
the registry explicitly reads only 2. Requests/observations declaring 1 fail.
The old inventory and implementation remain recoverable in Git history; the
current files are `adapter-contract.v2.json` and `coverage.v2.json`.

The Scripts state replaces `consent` with the observed `picker` flag and adds
`companions`, the relative modules actually resolved by the active owned
engine. Inputs are ordinary picker open/cancel/accept with the two owned local
source choices; a missing source is tested through normal URL entry. A running
engine or downloaded main file without advancing entity effects and actual
relative dependency resolution cannot pass. Entity-script consent remains in
the existing `scripted-entity` foundation.

This migration does not complete a platform adapter or qualify other draft
areas. Audio, Phone Graphics and platform-dependent Emotes still have the
source mismatches listed in `../FEATURE_SOURCE_COMPATIBILITY.md`; their
capabilities remain unavailable until corrected. Every other area still needs
its full source/input/independent-observer join. All devices remain untested.

# Original-source unlink fence mechanics

`OriginalSourceUnlinkFence` version1 extracts the existing Chat bounded-unlink
mechanics. The typed `ChatArchiveUnlinkFence` still requires its exact actual
`ChatArchiveReleaseSource` and fresh-phase policy. Other feature wrappers must
admit their own actual producer before using the shared mechanics. No observer,
input, source verdict, archive admission or public capability is supplied here.

The existing token shape and all source reads remain unchanged. There are at
most16 unlinks per250ms original native/host window, starting after acquisition.
The full original1.5s acquisition/final clocks still apply. Only preparation
before durable unlink intent may acquire a new source. Every actual unlink
still performs a new phase query after its last intent, followed by unchanged
cursor/physical/freshness checks. Failure retains the pending token and latches
the warm owner; no retry or cold adoption is introduced. Chat's clock lookups
remain late-bound to the same actual source/app objects and its token sequence
remains the original compiled-after native sequence.

Eighteen existing original unlink-fence and indexed-archive cases pass3.372s.
These include original clock jumps, phase/reader changes, physical replacement,
mutable cache rejection and copy/manifest/inventory changes. This is shared
mechanical reuse for the next Browser archive transaction, not its completed
feature or host closure.

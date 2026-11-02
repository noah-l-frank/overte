# Shared branch checkpoint — 2026-11-02

This checkpoint saves all pending work, including incomplete and unqualified
changes, on `test/android-pico/consolidated-adapters-20261027`. It preserves the
ten local commits after `411a13f61df10f2d9f6fde1fac626dda31248a47` and all 22
previously uncommitted files. The fetched remote tip was already their ancestor;
no previously integrated changes were removed or rebased.

Implementation stopped at the user's consolidation request. This checkpoint is
not a new complete-feature claim. No new builds, compiler invocations, device
tests, or feature implementation were started for consolidation.

## Pending work preserved verbatim

- Navigation: six files contain an unfinished G1 passive frame continuation and
  canonical binding integration. The last owning run was RED (21.141 seconds):
  the original 15 actions and a fresh G1 stereo acquisition completed, but the
  modeled native receipt inventory refused retirement. The proposed additions
  to foreign retired-capture guards in `graphics_binding.py` and
  `tablet_web_binding.py` were not implemented. No owning process remains.
- Lifecycle: `lifecycle_actor_storage.py` is an incomplete, untested V2 storage
  draft, including known signature-order and capacity-accounting corrections.
  It is not integrated with the existing Actor. The existing format's
  14 parts per observation exceeds the unchanged 512-part bound before the
  minimum 51 Common observations; this limitation remains unresolved.
- Create: the independent Model peer source/parent and its seven-file packet are
  retained. Before the stop request, 11 new source tests and 19 existing Parent
  tests passed. Production observer CLI/factory integration, a physical second
  client, complete Actor, GPU/stereo and global archive remain open. The new
  source tests have not been added to the central Pico catalog.
- Browser: the four-file archive namespace guard packet is retained. Before the
  stop request, its 21 owning cases passed. The previous complete Browser
  archive runs timed out at 120 seconds; no complete-run success is claimed.
- Catalog and coverage: the four pending Avatar/Audio/Lifecycle selector entries
  and coverage edits are saved as they stood. No additional registration or
  capability promotion was performed during consolidation.

The whitespace inspection reports one extra final blank line in the new
`create_peer_parent.py`; it is preserved verbatim with the rest of the WIP.
No feature test suite was run as part of this consolidation.

Scripts, Authentication and Graphics remain the three source-complete areas;
the other eleven areas remain partial. Native compilation and device
qualification are not established by this checkpoint.

## Local recovery

Before committing this checkpoint, a private backup captured all 22 original
file bytes, tracked/index patches, SHA-256 inventory and a verified full-history
Git bundle:

`/home/user/.local/state/overte-pico-shared-branch-save-20261102-g2t41n6a`

The original worktree stayed unchanged during capture. Feature-specific retained
host evidence remains in the existing private evidence directories; it is not
published as device qualification or added to the repository.

# Paused Pico feature-adapter source backup

This branch retains the complete committed adapter history and the separately
saved source changes from the paused session. The snapshot base is
`24772db8a343dce1ac3e9847cf8ead43c8f1f575`.

**Adapter development remains paused.** Authentication, Graphics and Scripts
are the three complete source-level areas out of fourteen. Devices are untested.
The other areas contain partial implementations and unresolved verification
work. Uploading these files does not complete or qualify a feature.

## Saved changes

The following source packets preserve unintegrated implementations, helper
sources, required dependencies and separately identified historical variants.
Each area has a README and hash manifest. Patch files are archival source;
they have not been applied to the live adapters. Some variants are alternatives
and must not be applied together. Review the area manifest before reuse.

| Area | Source packet |
| --- | --- |
| 1. Worlds/navigation | [Navigation](navigation/README.md) |
| 3. Avatar/contacts | [Avatar](avatar/README.md) |
| 4. Create | [Create](create/README.md) |
| 5. Emotes | [Emotes](emotes/README.md) |
| 6. Web in the world | [World Web](world-web/README.md) |
| 7. Web in the tablet | [Browser](browser/README.md) |
| 9. Audio | [Audio](audio/README.md) |
| 10. Chat | [Chat](chat/README.md) |
| 11. Snapshots | [Snapshots](snapshots/README.md) |
| 13. Assets | [Assets](assets/README.md) |
| 14. Lifecycle/input | [Lifecycle](lifecycle/README.md) |

Areas 2, 8 and 12 are retained in the implementation and commit history.
Files already present in the base tree are identified by the area manifests;
their unchanged contents need no additional application.

The [publication manifest](MANIFEST.json) records every saved artifact and its
SHA-256 digest. Patch syntax was checked without applying the experiments.
Existing test results retain their original scope and source epoch; this backup
adds no behavioral test, Native compilation or device qualification.

Runtime originals, generated credentials/certificates/configuration, private
environments, device/account selectors, binaries, complete temporary mirrors
and execution logs remain local. They are not source changes and are not part
of this publication. Source snapshots keep the existing timeout, budget,
cleanup and missing-capability failures explicitly unresolved.

Archived patches retain their original bytes and existing whitespace. A
directory-local Git attribute applies only to these patch artifacts; ordinary
source and documentation checks retain their existing rules.

Older local source stashes are also preserved under `stashes/` before deleting local task material. They remain inactive archival snapshots.

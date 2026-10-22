# Tablet original packet segments

`TabletWebSourceSegments` stores exact original source bytes in private files.
The closed `tabletweb-sources` profile uses one independent namespace per actual
source component and preserves the actual primary or actor role. Each source has
its own existing 1,024-frame bound; the underlying frame limit remains 1 MiB.
Each payload chunk contains at most 512 KiB of original bytes. Parent payloads
remain bounded at 4 MiB. No native packet is translated or resized.

The caller supplies an actual query digest and durably stores every parent and
child planned, opened and saved transition before proceeding. Interrupted
prefixes retain their real inode, bytes and hash. A complete opened file can be
read after a lost flush return without rewriting it or changing the stored
phase. Planned files must be genuinely absent; dangling links do not qualify.
Hardlinks, replaced files and changed partial prefixes fail closed.

This is byte ownership only. The caller must independently validate native
schema, original query, privacy policy, process, clock and history before writing
source bytes. A segment descriptor establishes no product effect, native
cleanup, input delivery or current source qualification. Inspection and read
perform no native request and never replay an interrupted write.

`OriginalPacketSegments` also has the closed `avatar-tail` profile. The Avatar
v1 facade retains its exact parent and body keys, filenames, namespace, hashes
and public API. An independently authored literal old Avatar envelope and
original file are read without changing their bytes or inode.

Host verification covers 2 MiB real payloads, the largest valid UIKit2 fixture,
partial empty files, a complete file after a lost flush return, hardlinks,
same-inode partial changes, dangling links, namespace separation and the literal
Avatar v1 boundary. Native code remains uncompiled and unexecuted.

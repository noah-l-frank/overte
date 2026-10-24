# Same Lifecycle primary graph through normal Chat and background

This extends the same private `PicoLifecycleOperations` class through actions
5 to 7 of the unchanged v16 recipe. The existing live Source3, World, Restore,
Editor and X owners remain. Lazy Chat/Background factories create the original
owners under the same source lock; their actual preparations are attached
before further observation. Normal Chat entry/focus/reply never sends text.
The existing Background owner performs its original arm, HOME, resume, both
full quiet windows and release. No second journey or mutating World is created.

Chat's optional typed fence extends its own durable intent/final navigation
callback. Background's fence marks before arm/release intents and HOME/resume
CAS, independently checks phase after those writes, and reaches the actual
Pico facade's once-only OS route. Its native app-file sender also rechecks after
its last guard for the typed Lifecycle fence; other existing fence/default
paths retain their behavior. Background phase admission requires no Qt or
foreground query. Pending's callback ownership is still untouched.

## Actual continuous result

Evidence directory:
`/home/user/tmp/overte-pico-lifecycle-continuation-20261024-sCdPTg8o`.
The materially changed final-identity positive passed **1/15.651 s** in
`lifecycle-operations-seven.log`, source SHA
`a61d977e9678ca01466c4b06ad5b1c0b149461b8c256b8161deb1f54be0a37aa`
(13485 files, unchanged), originals `lifecycle-editor-ms3ui14d`.

| Action checkpoint | World triples | Readonly triples |
| --- | ---: | ---: |
| 1 | 2 | 6 |
| 2 | 2 | 9 |
| 3 | 17 | 12 |
| 4 | 19 | 25 |
| 5 normal Chat open/focus | 19 | 28 |
| 6 normal reply draft | 19 | 31 |
| 7 original HOME/resume/quiet/release | 48 | 34 |

These are **82 World/readonly triples**, not a claim counting every different
kind of native getter. Editor/Chat/X original UI observations and the native
background timer/history also remain fully retained in their original owners.
An offline full-container read of the unchanged result reports:

| Original container | Children | Unpacked container bytes | Logical bundle bytes | Actual stored bytes including root | Files |
| --- | ---: | ---: | ---: | ---: | ---: |
| Primary observations | 136 | 168391 | 372636 | 237807 | 137 |
| Original phase metadata | 114 | 75535 | 114931 | 134029 | 115 |
| Background originals | 147 | 1320922 | no bundle layer | 220265 | 148 |

The offline report `lifecycle-operations-seven-offline-bill.json` verifies
original hashes/decoding and unchanged file stamps; it is historical storage
evidence, not another observation. World128, readonly128, each container's
512-child/16 MiB unpacked-raw limits, logical bundle budget and private-file
64 KiB remain unchanged. Process next-PID2…64 is separate. No full sixteen-action
budget fit is asserted.

Three disjoint BG counters passed **3/25.710 s** in
`lifecycle-operations-background-faults.log`, source SHA `a7380f80040c62d73854a8a95f1ae82f8dc10e39aed80d13540a7c4b0ff3f54f`:
phase change after HOME CAS prevents HOME; change after resume CAS prevents
launch while genuinely backgrounded in the model; change in the arm's final
guard prevents native mutation. Applied/uncertain intents remain retained and
no second call resends them. The same source's selected seven prior operation
guards, four canonical factory cases and two unchanged Chat/BG legacy cases
passed **13/25.388 s**, `lifecycle-operations-seven-regression.log`.

Initial setup failures are retained: double fixture/coordinator attach
(5.852 s) and a missing `number` import (5.695 s). Their concrete corrections
preceded the first continuous green (15.316 s). The later 15.651 s result above
also includes the actual final-identity correction below. Existing fixture
initialization is reused after the already executed normal actions; those
actions are not stubbed, replayed or replaced by expected observations.

## Correct actual outer-exit ownership

Three counters against exact unchanged core commit
`96230383238748547826434dd9c0a5c9fdbc0317` were **RED3/2.090 s**:
remove the parent after act; remove it after observe; or replace the actual
PhaseFixtureReader at real outer lock exit with unchanged URL/clocks. The old
core incorrectly delivered acknowledgments/observations. Original source bytes
SHA256 `d3b87e035e2c35847b5c96d47279e9a63b234c5822611354ee2a962852e6d564`
were loaded only into an isolated test module, with no worktree rewrite.
`lifecycle-operations-outer-exit-red.log` and original roots
`wr6k7ktn`, `0iq38ujj`, `06ptap8n` retain this evidence. Parent bytes were copied
byte-for-byte before the deliberate removal fault.

The new lock-free `identity()` is shared with `bound()`. It verifies exact
parent value/physical stamp, original directory, scope, phase reader/client/URL,
chunk identities and raw ledger. Own successful CAS pins only the actually
landed original parent. The guard runs after real outer exit, before/after
external source guards. Observe's optional `fresh(after_guard=...)` calls it
after the existing source guard and before the same original clocks/age check;
the default path and wire remain unchanged. There are no new samples, HTTP,
input or source renewal in this guard or locked session callbacks.

The same three counters are **GREEN3/2.124 s** in
`lifecycle-operations-outer-exit-fixed.log`, source SHA
`52128905ca1222dec350ae0e3eeb7d2c0e75c34497484a9d24a5ce38311d9de1`.
No landed output is reclassified as success after later ownership failure.

## Integration and remaining work

This packet follows `96230383238748547826434dd9c0a5c9fdbc0317` and its fixed
Source3 dependencies. One new `lifecycle-primary-operations` selector contains
all 14 operations cases, including the prior seven moved intact from baseline.
Baseline retains its eight original cases plus four factory cases (12).
The two selections are disjoint and keep 120 s each; no whole test is split.
The new selector joins existing OpenXR/tablet coverage rows. Local catalog
234 is only this branch's count; preserve Root's current entries and add one.
No new registry contract or version change is needed beyond the prior private
operations entry. Existing cold owner roots remain refused, never migrated.

The actual new Pico runner selector passed **14 cases/59.613 s**, selector
**1/234 groups/60.139 s**, below its unchanged 120 s cap:
`lifecycle-primary-operations-selector.log` and `.xml`. No worktree edits took
place during it. Its explicit full-source snapshot was captured after selector
start (not represented as a pre-start manifest) and matched after completion:
SHA `3cdba59e22cf04e93234b3d5ae71772733925ea9f3ade63f5f541aee3e199c04`,
13487 files. The earlier direct cases retain their actual before/after manifests.

Native/Qt/OS/physics and final I/O seams remain explicit models. There is no
`execute`, independent Actor, image or public capability substitute. Next are
the same class's normal Scripts/held/stale/Close/release/Restore actions8…16,
then the actual new-process cleanup-source handoff and full Actor/image/
resource/file/archive/host closure. These results do not qualify a whole feature.

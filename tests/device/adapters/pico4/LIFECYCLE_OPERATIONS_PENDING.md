# Same Lifecycle graph through Scripts and Pending quiet

The same private `PicoLifecycleOperations` now performs actions8–12 of the
unchanged common v16 recipe, after its existing normal Create/X/Chat/HOME
prefix. It uses the existing `PicoLifecyclePending`, normal Scripts entry,
native focus/type/hold/attempt/release and original X session. No second
journey, World, source cursor or substitute witness is introduced. Existing
`Journey.wait` runs at every checkpoint. Native Qt/IME/OS/physics/controller
and final app-file transports remain explicit host models, not device proof.

## Input and deadline ownership

Pending keeps its exact constructor-owned normal and native final callbacks.
An optional typed Lifecycle fence extends their existing intent/final-send
bodies; it never replaces them. The parent saves the exact phase before child
input. Independent original phase reads follow child CAS before final QML,
native and X publication. Controller callbacks under the original session
lock perform only already admitted host-age/envelope checks, never HTTP,
source acquisition or lock reentry. Actual Pico native publication retains
the installation/process guard. Only typed Lifecycle Pending `observe`
queries omit an issued-input phase check; mutations and other fences retain
their final checks. Three actual binding-sender counters cover this boundary.

One fixed twenty-second Pending segment begins before action8's preparation
and includes all five actions and intervening common waits. Child decorators
keep this deadline; later actions cannot renew it. It is cleared only after
the actual terminal quiet result. The original host hold birth remains
capture-start minus original native elapsed time, never reply-delivery time.

The **10000-ms hold is a maximum**, not a required wait. Original
`libraries/ui/src/ui/NativeFieldInput.cpp` starts `_timer` at10000; `expire()`
restarts an early timer only for the remaining duration; `observation()` and
`dispatch()` expire at elapsed>=10000. A different current context before
that ceiling records `rejected/context-retired`. The continuous fixture
observed that original terminal event at1000ms, then full three-second quiet.
No artificial delay or new birth was used. Native Pending's separate used-ID
cap is512, including observes; the existing owned-release exception remains.

## Versioned original reply retention

New Pending owner2 adds a parallel `replies` list, one slot per existing
durable mutation. A successful `operate()` exchange supplies its literal raw
reply, original command and already measured admission clocks. They are
preserved in the existing immutable original container **before the next
query**. No extra sample, source timestamp, mutation or clock read creates the
receipt. A lost exchange keeps its slot unknown; a later observation cannot
be relabeled as that reply. Failure cleanup has its own exact release slot.

Reply CAS uses the original physical/identity guards and full grammar even
when later live freshness has failed, solely to retain the already received
bytes. It grants no input authority. The same existing native/host1.5s,
exchange5s, segment20s and hold10s limits still run before successful return.
The landed-reply-CAS counter advances native time2000ms under fixed host:
the response remains retained, no next query occurs, the parent latches
failure and a second act cannot resend hold.

Existing owner1 reads/writes remain exact: no `replies` key, no rewrite or
automatic migration. Native wire and original-container versions remain1.
Operations2 adds only its fixed segment metadata and new route; existing
operation roots of either version still refuse cold live reconstruction and
remain owned. Registry changes are Pending2 reads1,2 and Operations2 reads1,2.

## Actual continuous evidence

Evidence directory:
`/home/user/tmp/overte-pico-lifecycle-continuation-20261024-sCdPTg8o`.
The materially changed reply-retaining positive passed **1/41.212s** in
`lifecycle-operations-twelve-replies.log`, full source SHA
`aa18627e70437ffd1ca452d57e0fe6fcbab38690bb4e99005a0e686c6d5f4811`
(13487 files, unchanged before/after). Originals:
`lifecycle-editor-j9lls0j_`. This is private primary-only execution1–12;
`execute`, peer, images, activation and reporting are forbidden test seams.

| Checkpoint | World triples | Readonly triples |
| --- | ---: | ---: |
| 7 returned background | 48 | 34 |
| 8 Scripts open/focus | 56 | 37 |
| 9 Retry draft | 59 | 40 |
| 10 original hold | 62 | 43 |
| 11 X/replacement Scripts | 66 | 46 |
| 12 stale attempt/release/quiet plus common wait | 85 | 59 |

These are144 physical World/readonly triples under **separate** unchanged
128-row bounds. They do not count every different native getter. There are
32 Pending-owner paired frames, five additional intent-only World reads,
five complete mutation replies (6034 raw bytes),13 terminal quiet frames,
and96 distinct original NativePending commands/sequence96. Segment start
19.852, completion24.852 and fixed deadline39.852 are fixture host times;
hold birth20.852 is not moved by archival or common waits.

The read-only historical bill `lifecycle-operations-twelve-offline-bill.json`
fully decodes original files/hashes and verifies unchanged stamps:

| Container | Children | Unpacked container bytes | Logical bundle bytes | Actual stored bytes including root | Files |
| --- | ---: | ---: | ---: | ---: | ---: |
| Primary Source3 | 236 | 315179 | 735881 | 435427 | 237 |
| Original phase packets | 192 | 155107 | 276099 | 253726 | 193 |
| Background originals | 147 | 1320922 | no bundle layer | 220309 | 148 |
| Pending originals | 133 | 360694 | no bundle layer | 176658 | 134 |

This bill is historical storage evidence, not a fresh sample. Each container
still enforces512children/16MiB unpacked raw; bundle logical limits,64KiB
private files,48KiB packed parents, original codecs, all physical reads,
cadence, clocks and runner120s remain. New-PID Process2…64 is separate.

## Counter, compatibility and integration evidence

- Lost actual hold answer and phase change after hold intent CAS:
  **2/46.862s**, `lifecycle-operations-pending-failures-1.log`, source
  `8b77322aa602fd7e098908c5479f6cb1aa5c1e5de58246506a3264267db1d26f`.
- Native jump in the final hold guard passed in the next two-case run
  (50.593s total); that run was overall red only because the segment test
  expected `typed` before typing instead of actual `focused`. The corrected
  same segment case passed **1/22.884s** in
  `lifecycle-operations-pending-segment.log`, source
  `fc5d7ac2b1ee321a543fc7ed6a2e5ddc7097affe75e4eb022ca591a6645433c0`.
- Landed reply CAS then native jump: **1/23.832s**,
  `lifecycle-operations-reply-late.log`, source
  `7c695f20674c14c7802fa7b2d8f5121f2d8408e837e7393e4a03491b42d00176`.
- Actual V1 cold continuation, strict full reply grammar and ten unchanged
  native transport tests: **12/11.523s**, `lifecycle-pending-reply-versions-fixed.log`,
  source `d882e8a00fe24230c1cf509cf8e3bac3b32c7f9e357affab064ce5626722253f`.
  The earlier pure-test setup incorrectly selected the post-focus observe
  instead of operate reply (KeyError,0.001s); only that fixture was corrected.
- Actual final Pico sender3 plus unchanged LostHold/failure-release2:
  **5/21.306s**, `lifecycle-pending-transport-legacy.log`, source
  `71d9f3d5464158320f3e15051b78ebc107cbeaf1ccb85f7a6087ad47874547a1`.
- Full V2 cold reply decode without another query: **1/8.118s**,
  `lifecycle-pending-v2-cold.log`, source
  `aaeb82129930915d1ea9a58bf4c24e1ac4b4ed539726e9376bcdcdae0b637814`.

These source manifests are distinct; earlier counters are not relabeled as
executed on the final reply code. No unchanged whole/positive was repeated.
All originals and failure logs remain private in that evidence directory.

Four additive Pico selections retain120s each: pending-operations1,
pending-publication3, pending-deadlines2, pending-versions6. Coverage verifies
the12 new cases are disjoint and complete. Existing operations14 stay in
their original selector. ControlPlane adds the reply-version module. The
local catalog changes234→238; Root must add4 to its current catalog and
preserve all newer entries/risk rows. Dependencies are the unchanged chain
through `c74609b3e86a08b50dc5038b821875248d39b229`, not the dependency-only
`1c85b265eb1a6a37c14afb0fce0ca5178bab7d1b`.

Final source freeze `6c5b97e6783d034f376c471c25ad8aeda8b619788bc51a486cb5035076f56751`
passed coverage11/0.054s (all14 risk rows), registry, discovery12 new wrapper
cases/3 sender cases, diff and the four repository suites
`documentation-contracts`, `project-coverage`, `documentation`, `source-layout`
in3.24s. See `lifecycle-pending-final-checks.log`. Subsequent edits only add
this review evidence; the functional source remains that frozen source.

Review file list (17 files):

- `tests/device/adapters/pending_commit_owner.py` retains already measured
  exchange timing only.
- `tests/device/adapters/pico4/lifecycle_pending.py`, `lifecycle_operations.py`
  and `binding.py` connect the same live owners and actual final input fences.
- `tests/device/self_tests/test_pico_lifecycle_operations.py`,
  `test_pico_lifecycle_pending.py`, `test_lifecycle_pending_reply_versions.py`
  reuse original fixtures and cover continuous/fault/version paths.
- `android/vr/pico/tests/device/test_lifecycle_pending_operations.py` and
  `test_lifecycle_pending_phase_transport.py` expose the real runner groups
  and canonical final sender.
- `android/vr/pico/tests/pico4-test-suite.py`, `pico4-coverage.json`,
  `pico4-coverage-test.py`, `tests/device/run_control_plane_tests.py`,
  `contract-versions.json` and `validate_contract_versions.py` register the
  exact additive selections and version admissions.
- This document and `LIFECYCLE_PENDING.md` record boundaries and evidence.

Actions13–16, actual old/newPID handoff, independent Actor, original image/
surface provenance and resource/file/archive/host finalization remain open.
No full budget fit or public Lifecycle capability is claimed. The next step
is the same class's normal Close/World/Restore connection using this retained
graph and its actual remaining per-producer budgets.

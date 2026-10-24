# Rooted Emote inactive-phase fence

Feature 5 remains partial. This component performs no app Stop, process
retirement, SDK deletion or metadata retirement. Native/device qualification
and a genuine whole paired inactive-phase checkpoint remain outstanding.

The public fence entry requires the actual typed `IOSEmoteRootedOwnership`
decoder and validated `IOSEmoteRootedFinalArchive`. It reopens the original
paired seal and compares every actual current metadata path to its exact
frozen copy, including explicit absence. Nonmutable metadata and original
file signatures remain guarded; newly acquired scoped files must be reached
by the actual typed readers.

`read_with_retirement_floor()` derives an additional host completion bound
inside the same guarded original round. It includes all selected and latest
current role cuts, original Actor observation acquisitions, and **every retained
published** canonical `PhaseWitnessPublisher` receipt acquisition, including
later publications outside the selected three-pair window. The existing default
Ownership/Window/Publication results and original sealed proof bytes remain
unchanged. The floor is the maximum **original host-after** epoch. Neither
public sample beginnings, native epochs, server acceptance timestamps nor
the time spent decoding an archive can substitute for this completion bound.

Both original inactive cleanup-phase packets must retain the same run,
instance, ticket and retirement epoch. Retirement must follow the completion
floor. Fresh local rooted Scope3, global key and pointer originals extend the
existing quiet window while preserving all held resource identities. No
ordinary Emote Sources acquisition is attempted after fixture retirement.

Freshness uses original host epoch/monotonic brackets and the same-instance
native global key source's epoch/monotonic clocks. Native and host epoch
origins may differ. New immutable files are pinned before typed rereading
and the final external phase request. The original 1.5-second bound remains
unchanged.

Focused component tests use actual private original/copy files with explicitly
modeled native, phase and paired-measurement boundaries. They cover missing,
foreign, stale or active phases; wrong seals; new formerly absent metadata;
changed other-role metadata; equal-byte inode rewrites; expired acquisitions;
and retirement after a public sample starts but before its role/HTTP read ends.
These cases do not qualify the whole paired fence entry or process end.

An uncertain final phase response retains the actual extended local owners.
A later typed retry journal must reconcile that responsibility before process
integration; the current component does not silently replay an input or turn
this failed attempt into permission to Stop.

Eight local/frozen-seal/metadata cases passed in the combined 25-test clock/fence
run (48.680 seconds). Later completion-floor, ownership and journal regressions
passed in the 63-test Stop/floor/PCM run (17.697 seconds). A separate actual
retained normal-cleanup three-pair graph passed `read_with_retirement_floor()`
in 108.203 seconds: all 1,465 original files and 5,398 source files were unchanged,
with zero native observations and current copied-metadata reads forbidden.
Its original complete host-after floor was later than the public sample starts;
the original seal/proof remained unchanged. That corpus has no actual inactive
phase, so it cannot qualify full fence acquisition, Stop or SDK end. Its CPU
cost does not satisfy the complete operation budget.

Focused no-build entrypoints, additionally using the local private TMPDIR,
verification overlay, bytecode suppression and unique blocked-attempt log:

```bash
PYTHONPATH=.:tests/device:tests/device/self_tests:tests/device/ios/self_tests python3 -m unittest -v -f \
  test_ios_emote_rooted_fence.RootedFenceLocalTests \
  test_ios_emote_rooted_fence.RootedFenceSealTests \
  test_ios_emote_rooted_fence.RootedFenceMetadataTests \
  test_ios_emote_rooted_fence.RootedFenceRetirementFloorTests \
  test_ios_emote_rooted_ownership.RootedOwnershipTests \
  test_ios_emote_terminal_journal.TerminalJournalTests
```

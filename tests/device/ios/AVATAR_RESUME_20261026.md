# Avatar 3/14: explicit pause checkpoint

Work is paused at the user's request. No further test or optimization was
started after that request. Avatar capability remains closed; complete areas
remain 5/14. Native/SDK/renderer boundaries remain explicitly modeled and native
sources remain uncompiled. Historical profiles are not completed feature runs.

## Retained interrupted full host diagnostic

- Original entrypoint:
  `ios.self_tests.test_ios_avatar_held_terminal.AvatarHeldTerminalTests.test_baseline_cleanup_preserves_login_holds_until_paired_os_and_sdk_end`.
- Actual original graph and log:
  `.ios-host-tmp/avatar-full-held-metadata-20261026-kww7630a/runner.log`.
- Its outer diagnostic limit was 600 seconds. Production API, native/source,
  file and freshness limits were unchanged. Only actual Scene entry/return
  counts, caller phases and host elapsed time were instrumented.
- The user requested pause before that outer limit. SIGTERM was sent to the
  exact owned timeout process (PID 216485); tool session 33413 terminated with
  **exit 143**. A subsequent `/proc` census matching that exact private `TMPDIR`
  found **no remaining processes**. Original files were retained.
- Last log: Actor Scene entry **count 9, reference 2**, phase
  `joined/derive/retirement_original/original/publish/publish_scene`, at host
  elapsed **141.010 seconds**. Actor entries 1–8 and Primary 1–4 had returned.
  No successful Scene-publication return, logout/final/end or full test pass
  was observed. No unknown publication may be resent on the basis of this
  trace; inspect actual publisher/fixture originals first.

## Committed source packets

All reviewed Avatar source/test packets are already committed locally:

- `4e423d95f0`: actual closed Avatar Scene5 receipt/publisher/reader integration;
  literal older stages and Complete writer2 remain unchanged.
- `f0cac05ae0`, `5809b3cd8b`: raw manifest reuse with separate plain/collector
  read sets, immutable context and original frame checks.
- `b68116a302`: canonical Avatar routing, failed/terminal SDK-free qualification
  and original metadata CAS, with the capability still closed.
- `cd0c39c30f`: fresh parsed original frame returned without a redundant copy;
  every original byte/inode/hash/deadline/read-membership check remains.
- `6db9a540d1`, `791583d0fa`: isolated Avatar pure-validation profile and literal
  historical State/Renderer validation reuse; live/current validation remains.
- `dd829a6f5e`: terminal fixture uses actual private SDK/Installed files. The
  existing modeled Installed original was moved before first admission with
  unchanged device/inode/bytes; actual reset/frozen decoding/CAS paths execute.

Recent explicit focused selections passed: canonical routing/budget 30 cases,
fresh-frame read 42, guarded pure Scene 32, historical DTO wrappers 36, and
private metadata fixture/routing 23. Their private logs and exact qualifications
are documented in [canonical routing](AVATAR_CANONICAL_ROUTING.md),
[manifest indices](AVATAR_MANIFEST_INDICES.md), and
[historical Scene costs](AVATAR_FRAME_READ_COST.md). These counts overlap and
must not be added as distinct tests or promoted to whole-area acceptance.

## Resume boundary

Continue only after the user resumes. Re-read this checkpoint and the root pause
handoff, verify the own worktree/branch and shared source ownership, and preserve
all retained private graphs. Do not change product sources/pins, production
deadlines, original timestamps, bindings, resource identities or uncertain-input
semantics. Do not start device/build/lab/install work under this source task.

The corrected private-metadata fixture has focused qualification, but the full
paired held end, actual canonical per-role metadata CAS/repeated cleanup,
production Actor exit and unchanged full Avatar journey remain open. The next
integration work should use the actual interrupted log and original journals;
it must not report historical profile improvements as closure. No ordinary
operation or cleanup may silently recreate a deleted SDK or discard unresolved
ownership. Coordinate any next heavy host run and shared Git index with root.

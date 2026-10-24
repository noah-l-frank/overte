# Lifecycle restore/process packet review

This packet joins the existing editor/pending/close prefix to normal location
restoration and the existing process-restart owner. Public capability, common
peer/image execution and final file retirement remain unqualified. Qt, physics,
domain and OS producers in the host case are explicitly modeled boundaries.

## Dependencies and changed files

Select only this packet after `5cd9415e093c27d64ea6ba6ded0ffe0dbdb0b702`
(Root selection `5953ba3ebb`). Root already has the pending/binding fixes from
`c2ade13a0ac24bf71e28e633a099df890207e6bd`. Do not select dependency-only
`1c85b265eb1a6a37c14afb0fce0ca5178bab7d1b` again. Existing final QML and
controller admission/publish hooks are reused; no Phone or moving WIP is copied.

Exact files, all under the repository root:

- Runtime: `tests/device/adapters/pico4/{binding.py,lifecycle_process.py,lifecycle_restore.py}`.
- Shared tests: `tests/device/self_tests/{test_token_lifecycle_ui.py,test_pico_lifecycle_restore.py,test_lifecycle_process_compatibility.py,test_lifecycle_process_finalization.py}`.
- Pico wrappers: `android/vr/pico/tests/device/{test_lifecycle_input.py,test_lifecycle_restore_owner.py,test_lifecycle_process_v2.py,test_lifecycle_process_finalization.py}`.
- Pico registration: `android/vr/pico/tests/{pico4-test-suite.py,pico4-coverage.json,pico4-coverage-test.py}`.
- Control plane: `tests/device/{contract-versions.json,validate_contract_versions.py,run_control_plane_tests.py}`.
- Documentation: `tests/device/adapters/pico4/{LIFECYCLE_RESTORE.md,LIFECYCLE_RESTORE_REVIEW.md}`.

## Wire, source and delivery boundaries

Two registry entries change: process current 2/reads 1,2, and new restore owner
1. Existing process-v1 bytes/layout/connected-Chat2 rules remain unchanged.
New process-v2 accepts actually observed NativeChat2/3 disconnected state without
inventing a connection birth. Connected mixer/domain/birth checks remain strict.

Only new process-v2 uses XZ6 during preparation and XZ6EXTREME for the once-final
`process-retired` state. World-v2 stays preset3; historical World snapshot bytes
and v1 zlib bytes are unchanged. Raw16MiB/Base6448KiB/private-file64KiB and
decoder16MiB/original-size-plus-one/EOF/hash/canonical limits remain unchanged.
The same World128 journal counts every authoritative restore/Prepare sample.

Process.begin precedes the first existing editor input. A private normal-address
surface admits only the path from the original feet/quaternion. AddressManager's
path-only branch preserves the exact original scene URL. Actual restored quiet
serves Prepare and immediate require_stop_ready; no mandatory query is removed.
Intent precedes Native acquisition, its answer precedes Domain acquisition,
and one atomic pair commit retains both before another query. Unknown reads
remain pending. No fallback overwrites a possibly landed pair commit.

V2 copies the report before actual lock exit. Delivery then checks journal and
report hashes, installation, all new source/PID guards, actual Native clock and
Host monotonic age against the same original epochs. The restart helper repeats
only these checks after its own actual outer lock exit. Late refusal retains the
landed state and clears the live delivery handle; phase alone is never success.

## Exact evidence and registration

Private evidence root:
`/home/user/tmp/overte-pico-lifecycle-continuation-20261024-sCdPTg8o`.

- Positive: `restore-final-v2-positive.log`, 1/23.794s, originals
  `lifecycle-editor-eln5pxqm`. Source/runner manifest
  `restore-final-v2-source-manifest.json` SHA `bfa812798ac886511c3b9c35a6eb193db48cdc4bb0618eacb28e1544a4dfe8e3`
  matched before/after. World125/128, 125 unique nonces per UI/gesture/drive,
  Prepare13 pairs, new-process13 frames. Final file47,912B/Base6447,692B/raw1,446,029B.
- Actual final-fence RED1/5.464s then GREEN4/21.816s:
  `process-final-counter-{red,green}.log`. Landed-save, report-build, new-process
  guard loss and actual outer restart-lock exit are covered without resampling.
- Functional compatibility: `process-version-compatibility.log`, v2 14/81.695s,
  v1 14/18.935s. Focused codec/domain/World-cold-snapshot4/1.272s:
  `process-codec-policy-compatibility.log`.
- Known separate v1 requirement failure: `process-v1-final-age-requirement-red.log`,
  1/1.338s, originals `lifecycle-world-uwvxecu4`. V1 accepted a late Native jump;
  neither skip/expectedFailure nor compatibility green declares that safe.
- Earlier real limits remain documented: lost early-setup evidence0.113s,
  retained first-Prepare48KiB refusal12.388s and final-save refusal23.785s.
  Their complete later failed states and offline comparisons remain private.

Three new selectors, each120s: `lifecycle-restore-owner`1,
`lifecycle-process-v2`14, `lifecycle-process-finalization`11 after the separate
v1 follow-up (four fences per version plus three compatibility cases).
Existing `lifecycle-input-owner` retains its14
explicit v1 cases. Discovery was checked without running cases: 1/14/7 and14,
no imported fixture duplication. Local catalog228→231; Root must add three to
its own current total. Control-plane patterns add the three new shared modules.
No whole execution is split to evade a timeout.

Final lightweight validation: registry coherent; Pico coverage10/0.041s maps
14/14 risks; four repository suites passed in 2.83s (`documentation-contracts`,
`project-coverage`, `documentation`, `source-layout`). No build/device run.

## Separate v1 delivery-freshness follow-up

Depends on `84d122721b2c8380017ed2bf12a8ac1ba5490264`; no new selector or registry
entry. The shared final-delivery guard now also checks v1 after report build and
actual observer/restart lock exits. V1 writer/layout/domain/snapshot bytes stay
unchanged. The same previously red requirement plus report, new-PID guard and
actual outer-lock edges passed4/5.366s (`process-v1-finalization-green.log`);
positive retirement/lost-stop/lost-launch/cold byte compatibility passed4/7.331s
(`process-v1-positive-compatibility.log`). Four v1 cases join the existing final
selector; earlier1/14/7 discovery remains historical and becomes1/14/11.
No new source sample, replay, schema migration or public capability is added.

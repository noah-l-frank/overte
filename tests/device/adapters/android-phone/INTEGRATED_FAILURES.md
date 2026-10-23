# Combined Android Phone campaign failures

The completed Jenkins build **3** recorded **7 PASS, 5 FAIL, 57 ERROR** across
69 target rows, with no aggregate skips. Source composition exists for all
14 areas and the matching APK compiled, but all 14 full feature journeys are
ERROR. No full feature/device acceptance or other-client qualification follows.

## Five actual FAIL targets

| Target | Original target status / return code / seconds | Aggregate reason |
| --- | --- | --- |
| domain-enter | FAIL / 1 / 4.203 s | module-result |
| domain-roundtrip | FAIL / 1 / 8.659 s | module-result |
| multi-user | FAIL / 1 / 8.842 s | module-result |
| network-fault-recovery | FAIL / 1 / 8.904 s | module-result |
| tablet-e2e | FAIL / -15 / 180.101 s | module-result |

These are actual failed targets. Status and log digests alone do not establish
a product root cause. The `tablet-e2e` return code -15 and duration 180.101 s are
preserved without inferring a different failure or successful cleanup.

## All 57 actual ERROR targets

The setup/infrastructure column preserves original nonpassing and missing setup
results. An original target SKIP is not promoted to a green aggregate result.
“Not recorded” means no original target row was retained, not proof that a
particular device action did or did not occur.

| Target | Original target status / return code / seconds | Setup / infrastructure | Aggregate reason | Original classification |
| --- | --- | --- | --- | --- |
| feature-world-navigation-required | ERROR / 75 / 0.084 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-authentication-required | ERROR / 75 / 0.085 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-avatar-people-required | ERROR / 75 / 0.085 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-create-required | ERROR / 75 / 0.083 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-emotes-required | ERROR / 75 / 0.087 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-world-web-required | Not recorded | None required | missing-summary | NO_ORIGINAL_MODULE_SUMMARY_OR_EXECUTION_PROOF |
| feature-graphics-required | ERROR / 75 / 0.085 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-audio-required | ERROR / 75 / 0.086 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-chat-required | ERROR / 75 / 0.082 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-snapshots-required | ERROR / 75 / 0.086 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-assets-required | ERROR / 75 / 0.084 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-lifecycle-input-required | ERROR / 75 / 0.083 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-tablet-web-required | Not recorded | None required | missing-summary | NO_ORIGINAL_MODULE_SUMMARY_OR_EXECUTION_PROOF |
| voice-roundtrip | ERROR / 75 / 0.132 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| update-upgrade | SKIP / 77 / 0.0 s | scene:ERROR | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| scene | ERROR / 75 / 9.412 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| spawn-grounded | ERROR / 75 / 5.072 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| world-interaction | ERROR / 75 / 4.864 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| scripted-entity | ERROR / 75 / 4.98 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| text-input | ERROR / 75 / 34.756 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| settings-persistence | ERROR / 75 / 0.0 s | Passed | module-result | TARGET_PRE_PROCESS_OR_CAPABILITY_ERROR |
| lifecycle-under-load | ERROR / 75 / 5.235 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| render-health | ERROR / 75 / 5.192 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| entity-sync | SKIP / 77 / 0.0 s | domain-enter:FAIL | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| crash-recovery-under-load | ERROR / 75 / 5.279 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| asset-load | SKIP / 77 / 0.0 s | scene:ERROR | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| sound-playback | SKIP / 77 / 0.0 s | scene:ERROR | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| look | ERROR / 75 / 4.96 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| move | ERROR / 75 / 5.042 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| input-neutral | ERROR / 75 / 5.075 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| collision | ERROR / 75 / 5.074 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| scene-reload | ERROR / 75 / 8.462 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| jump | ERROR / 75 / 5.109 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| fly | ERROR / 75 / 5.118 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| tablet | ERROR / 75 / 5.101 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| tablet-input-isolation | ERROR / 75 / 5.219 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| world-web-video | ERROR / 75 / 0.105 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| tablet-web-video | ERROR / 75 / 0.088 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| snapshot-output-parity | ERROR / 75 / 5.098 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| scripts-management | ERROR / 75 / 0.093 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| create-management | ERROR / 75 / 0.105 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| accessibility | ERROR / 75 / 0.099 s | None required | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| places-navigation | ERROR / 75 / 5.377 s | Passed | module-result | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-world-navigation | SKIP / 77 / 0.0 s | feature-world-navigation-required:ERROR, launch-smoke:SKIP | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| feature-authentication | SKIP / 77 / 0.0 s | feature-authentication-required:ERROR, launch-smoke:SKIP | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| feature-avatar-people | SKIP / 77 / 0.0 s | feature-avatar-people-required:ERROR, launch-smoke:SKIP | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| feature-create | SKIP / 77 / 0.0 s | feature-create-required:ERROR, launch-smoke:SKIP | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| feature-emotes | SKIP / 77 / 0.0 s | feature-emotes-required:ERROR, launch-smoke:SKIP | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| feature-world-web | Not recorded | missing:feature-world-web-required, missing:launch-smoke | missing-summary | REQUIRED_SETUP_RESULT_MISSING |
| feature-graphics | SKIP / 77 / 0.0 s | feature-graphics-required:ERROR, launch-smoke:SKIP | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| feature-audio | SKIP / 77 / 0.0 s | feature-audio-required:ERROR, launch-smoke:SKIP | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| feature-chat | SKIP / 77 / 0.0 s | feature-chat-required:ERROR, launch-smoke:SKIP | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| feature-snapshots | SKIP / 77 / 0.0 s | feature-snapshots-required:ERROR, launch-smoke:SKIP | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| feature-scripts | ERROR / 75 / 5.905 s | Passed | observer-required-forced-cleanup | TARGET_MODULE_PROCESS_COMPLETED_ERROR |
| feature-assets | SKIP / 77 / 0.0 s | feature-assets-required:ERROR, launch-smoke:SKIP | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| feature-lifecycle-input | SKIP / 77 / 0.0 s | feature-lifecycle-input-required:ERROR, launch-smoke:SKIP | setup-not-passed | REQUIRED_SETUP_NOT_PASSED |
| feature-tablet-web | Not recorded | missing:feature-tablet-web-required, missing:launch-smoke | missing-summary | REQUIRED_SETUP_RESULT_MISSING |

The Scripts gate passed, while its original journey returned ERROR/75 after
5.905 s. Its aggregate `observer-required-forced-cleanup` error remains recorded
separately. Four World Web/Tablet Web rows lack original summary/log proof.
The 49 target-log completions and 65 original summaries establish host execution
and status provenance only; they do not prove 69 physical device journeys.

## Preparation gaps

The [37 exact preparation ERROR rows](integrated-preparation-errors.v1.json)
remain distinct from campaign outcomes. Missing genuine domain, image geometry,
HTTPS/account, independent Phone/PC peer and native-worker inputs were not
replaced by expected observations or simulated capabilities. The original
assignment client ended with `std::bad_alloc` before domain READY; resource/root
cause remains unknown. Earlier Jenkins builds 1/2 stopped before tests and keep
their separate approval/compilation failures.

## Cleanup boundary

Both exact task-owned HTTP fixture groups were retired successfully. The task's
native backend container was stopped with no owned survivors recorded. These
are scoped fixture cleanup results, not global host or device closure.

A separate host audit identified an SDK ADB daemon with inherited bootstrap
state, but outside the frozen mapped transport namespace and with two live
connections. Inherited environment/cwd do not establish exclusive task use. It
was retained **without signals** to protect possible other sessions. Three
same-UID process environments could not be read; no global host/transport
cleanup is claimed.

The separate pre-campaign Tablet reference owner remains closing because its
original Appium session returns HTTP 404. No rebind, input replay or journal
deletion was used to manufacture cleanup success. This retained failed
preparation owner is separate from the 69 target status records.

See [all actual statuses and evidence hashes](integrated-campaign-results.v1.json),
[the current coverage matrix](INTEGRATED_COVERAGE.md) and
[the integration campaign handoff](INTEGRATED_CAMPAIGN.md).

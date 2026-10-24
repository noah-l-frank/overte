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


## Later focused repair evidence, 2026-10-24

The 69-row build 3 above remains **7 PASS, 5 FAIL, 57 ERROR**. These later
focused runs do not rewrite its results or qualify all fourteen feature areas.
The [campaign matrix](INTEGRATED_COVERAGE.md) retains that original campaign
scope; shared test logic, adapter source and actual device acceptance remain
separate.

The installed client remains source `0a7de4299f4bb97e99c844288e6381efd973df0f`
and APK `43ed8f0ad7e9e5fe4beaa7c39833441f42979ff209181eaf00e4ec933df41248`.
No new APK was built for these focused repairs. Harness and client inventories
were checked independently. The fixes are domain-input admission `a587adb0d7`,
owned evidence directories before discovery `abc645bba6`, fresh Tablet action
observations `c4ab97be44`, backend argument lifetime `cae3428bb9`, and the measured
registered Tablet budget `f7139affc5`. Exact approved Scene-query admission was
also corrected in `98acf88bf7` and `91d5533edd`.

| Scope | Test logic | Adapter/source | Actual device evidence |
| --- | --- | --- | --- |
| Tablet core journey | Original complete module; registered 300-second catalog | Harness `c4ab97be44`, catalog `f7139affc5`; individual freshness, capability and cleanup checks retained | Build 6 PASS: Tablet 204.195 s; launch 26.711 s. Historical 180-second budget was not retested. |
| Controlled Scene foundation | Original six-entity check; one stable sample | Harness `91d5533edd`; original query retained | Build 9 PASS: Scene 64.132 s; launch 25.717 s. This is not complete navigation or domain recovery acceptance. |
| Four domain foundations | Original modules and budgets | Harness `7c3ea1189a`; actual Scene V5 and separately built backend `cae3428bb9` | Build 13: launch PASS, all four domain modules FAIL. Scene cleanup, Native before/after identity and four isolated command owners were verified clean. |
| Create / Assets companions | Original observer/execute composition; 11 host counters PASS | External versioned Companion V3; genuine render inputs and independently credentialed roles still required | No full Create/Assets device result from these host counters. |
| Other full feature journeys | Existing shared logic and Phone source remain present | Mandatory missing inputs remain errors | No later complete fourteen-area acceptance; no Pico/iOS qualification. |

Build 13 is a real module-failure result, distinct from earlier preparation-only
errors: domain-enter 64.394 s, domain-roundtrip 68.713 s, multi-user 70.328 s and
network-fault-recovery 69.454 s, all return code 1. Its exact JSON/JUnit and
source/installed/Scene/native provenance joins were verified offline. All 83
collected adapter contexts completed their diagnostic observation; no malformed
probe body was observed. This does not establish a failure root cause.

Harness `7c3ea1189a` permits at most three fresh probe-file reads only after JSON
decoding fails; stale, schema and transport errors still fail. Its new
atomic C++ probe writer is future source and is **not installed** in the unchanged
APK. Native backend compilation/loader/READY evidence is infrastructure evidence,
not Phone feature acceptance. Independent actor-source requirements, a second
Phone where required, genuine image/HTTPS/account inputs and a compatible PC voice
peer or an independent Chat receiver remain mandatory; no historical or synthetic peer supplies them.

The retained public-summary SHA-256 values are:

- Build 6: `feaa5c6d880d37bb3235de4fd1a728acbd2ffaf8fbae87f898962a88afa99ee0`
  (also recorded in [Tablet calibration](tablet-budget-calibration.v1.json)).
- Build 9: `e1c3dbbb4180d8d8198d5210f36befced84fe47dfcb3f37290b479db220d27ad`.
- Build 13: `bd6cb3a78a617ddbba3f2f3c87e4c205b1e01f2867b567e77515908669f53fb6`.

The separately retained Companion V3 host-package SHA-256 is
`24b22545f7062836f765a72ca234a57cc910e01d0f1bcddfec94e1da960a40a2`.
Its 11 host methods passed in 19.578 s; they are not product or device proof.
These hashes identify retained evidence without publishing private logs, target
configuration or runtime credentials.


## Measured navigation transport calibration

Later Asset foundation build 14 recorded launch PASS (29.272 s), Scene ERROR
(69.723 s) and asset-load SKIP because its required Scene setup did not pass.
The Scene module duration is not the duration of one adapter operation. Actual
spans show normal navigation still progressing through 58.787 s before its
60-second outer transport deadline; the final native-process span has no end,
so neither its duration nor an ADB hang is established. The earlier Scene build
9 completed the same normal input in 53.729 s.

The initial named `scene.load` and `navigation.enter-domain` transport calibration
set both limits to 90 seconds. All other operation limits and the original 120/180-second module
budgets remain unchanged, as do fresh candidate/process/UI observations,
capabilities, source guards and cleanup. No cache, observation substitution or
new APK was introduced. This initial measured harness calibration awaited a
fresh device run; it did not convert build 14, the skipped Asset target or the
original campaign to PASS.

Build 14 public summary SHA-256: `b54486d8a19bfe1a76e5cbb74f0159e415e091390fdfbe0dbe403ece5301751c`.
The censored original adapter span SHA-256 is
`609fac1a5911ba51fe4edee147b151d7b659756400abe5bb63b54c029f59ff3e`.


Focused domain-entry build 17 subsequently recorded 37 fresh installed-identity
checks costing 57.130 s inclusively (nested candidate/ADB costs overlap). Its W3C
POST/click response was acknowledged at 73.242–73.371 s after navigation began;
this does **not** prove that Go activated, a user press occurred or navigation took
effect. The address field was still observed at 82.696 s, and the configured
20-second post-click validator was censored by the outer 90-second limit. Only
`navigation.enter-domain` now receives 120 seconds; `scene.load` stays at 90,
with the original 180-second module and 20-second UI bounds and all fresh guards
unchanged. Build 17 remains ERROR; this transport calibration neither replays Go
nor claims a product fix, device PASS or new APK. The original span SHA-256 is
`2723528f0fbdd102ab3288bbf8f3572daf5676a9ab2b16ff5b6f1b000d787b05`.

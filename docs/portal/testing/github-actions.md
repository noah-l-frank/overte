---
last-reviewed: "2026-10-22"
scope: "Current selective CI, live required-result inventory, and private laboratory boundaries"
---

# GitHub Actions

This is the CI of **noah-l-frank/overte**, a personal hobby fork. The
maintainer's [private Jenkins laboratory](../jenkins/index.md) runs separately
on Proxmox. Access to that infrastructure is not a prerequisite for reading the
code or running host tests. These workflows do not promise hosted build
capacity, contributor support, or a release schedule. A green PR or a packaged
application does not establish physical-device acceptance.

The [selective PR CI guide](https://github.com/noah-l-frank/overte/blob/main/docs/PR_CI.md)
owns the current controller, selection, isolation, and acceptance contract.
[Platform coverage](https://github.com/noah-l-frank/overte/blob/main/docs/PR_CI_PLATFORM_COVERAGE.md)
owns the browser, Android, and iOS execution tiers and their prerequisites.
Follow those guides when integrating locally prepared CI changes; historical
workflow recipes and earlier rollout reports do not define the current gate.

## Required repository checks

The live rules for all seven permanent branches were read on **October 22,
2026**. They require these two shared GitHub Actions results:

| Required result | Responsibility |
| --- | --- |
| `source-policy` | Authenticate the complete workflow and controller sources from trusted policy without executing candidate code. |
| `required-ci` | Independently authenticate selected execution owners, their actual results, and the current PR candidate. |

Additional topology results remain required on these targets:

| Target branches | Additional required result |
| --- | --- |
| `main`, `android-main`, `apple-main` | None beyond the two shared results. |
| `android-phone`, `android-vr`, `android-vr-pico` | `Enforce Android parent sync path`. |
| `apple-ios` | `Enforce apple-main sync path`. |

The former `repository-checks`, `sync-test-reuse`, `codeql-security-results`,
`dependency-release-policy`, `branch-policy`, and separate `ios-device-build`
contexts are not the current shared required-result inventory. Their historical
records remain useful evidence for their original revisions.

**Actions was disabled** at the same inspection. Installed source, local tests,
and live rules do not establish a hosted execution. Work still being qualified
locally must retain its own revision and evidence; an implementation draft is
not a completed native build or device test. Enabling Actions requires the
maintainer's explicit instruction.

To inspect the live rules without changing them, substitute the intended branch:

```text
gh api repos/noah-l-frank/overte/rules/branches/<branch> \
  --jq '[.[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context] | unique'
gh api repos/noah-l-frank/overte/actions/permissions --jq '{enabled: .enabled}'
```

This is a dated observation, not an instruction to apply repository settings.
Recheck the rules after a rollout or administration change. A successful manual
workflow or a similarly named job cannot replace a required result.

## Workflow entry points

The current `repository-checks.yml` controller selects work once from complete
immutable base and candidate trees. Its owners cover applicable policy, host,
package, native, platform, and CodeQL checks. Candidate execution and trusted
acceptance have separate authority. The final gate verifies the actual selected
native GitHub jobs and their source-bound execution record.

Consult the [current workflow directory](https://github.com/noah-l-frank/overte/tree/main/.github/workflows)
and selective CI guide for installed triggers and reusable recipes. Files under
`tools/repository-checks/workflows` also retain historical or staged generations;
their presence alone does not activate them. Earlier shared PR, synchronization,
and post-merge qualification recipes must not be treated as additional current
acceptance owners or restarted to repeat an already selected command.

Manual builds, release candidates, dependency preparation, maintenance schedules,
and explicit diagnostics have separate purposes and prerequisites. An existing
self-hosted recipe does not establish that its runner is available. The
platform-owned guides describe signing, artifacts, and manual build parameters:
[Android Phone](https://github.com/noah-l-frank/overte/blob/android-phone/docs/interfaces/android-phone/CI.md),
[Pico 4](https://github.com/noah-l-frank/overte/blob/android-vr-pico/docs/interfaces/pico4/CI.md),
and [iPhone/iPad](https://github.com/noah-l-frank/overte/blob/apple-ios/docs/interfaces/ios/CI.md).
Retention limits are defined in the [CI storage policy](../../CI_STORAGE_POLICY.md).

## Selected work and unchanged PR text edits

Selection reads actual input closures, including deleted paths, rename sources,
and file modes. Package changes retain their install, vulnerability, build,
and behavior checks. A package lockfile alone does not select an unrelated
Overte build. Browser journeys depend on the affected browser's application,
renderer, UI, or test inputs. Unknown inputs retain conservative coverage.

CodeQL covers the affected extractor inputs; changed shared analysis controls
retain both supported languages. Pending or unverified security results cannot
be reported as success. Dependency vulnerability queries execute against their
current advisory data rather than borrowing an old result.

A task fingerprint identifies inputs and execution requirements. Reuse also
requires independent authentication of the original successful command and its
native run, artifacts, source, and current context. Missing optional proof
causes execution. A matching cache or fingerprint alone is not a passing test.

PR metadata events do not create replacement execution evidence or a substitute
`required-ci`. The controller retains the original tested merge identity and
authenticates any equivalent regenerated merge using its base, head, parent
geometry, and complete tree. Changed sources require the applicable new work.
See the selective guide for the current event and receipt verification rules;
older metadata-retention recipes describe their original deployment only.

## Native builds

The central planner selects native work from relevant production, build, and
test inputs. Host-only selection does not imply product compilation. Platform
tiers remain distinct: Java/resource compilation is not an APK, a Qt host check
is not an IPA, and either package is distinct from physical-device acceptance.
Use the current platform coverage guide for required dependency graphs and
exact-source consumer prerequisites. A locally prepared follow-up must not be
described as deployed or qualified before its own checks finish.

The [native lane guide](../../../tools/native-tests/README.md) retains the native
build mechanics and earlier routing/deployment details. The
[September qualification report](../../NATIVE_CI_QUALIFICATION.md) records actual
build costs and a native failure that blocked a merge at that revision. Those
measurements and old result names are historical, not current latency guarantees
or an instruction to reactivate a former gate.

## Inspect a run

Open [the fork's Actions page](https://github.com/noah-l-frank/overte/actions),
select the exact candidate or integrated revision, and inspect the failed owner
before the final gate. Match actual job results, artifacts, and reused evidence
to the recorded source and run. While Actions is disabled, report local checks
as local evidence and keep hosted execution unclaimed.

A verified APK or IPA is build evidence. Installed-app identity and physical
behavior require their own checks in the private Proxmox Jenkins laboratory.
The retired workstation device lab is not a fallback.

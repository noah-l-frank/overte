# iOS continuous integration

The central selective PR controller in `repository-checks.yml` selects shared
and iOS consumers and reports `source-policy` and `required-ci`.
`Enforce apple-main sync path` remains a separate topology result. These are
the live required names read on October 22, 2026; `ios-device-build` is no longer
a separate required context. Actions was disabled at that inspection. See the
[shared CI overview](https://github.com/noah-l-frank/overte/blob/main/docs/portal/testing/github-actions.md)
and [selective CI guide](https://github.com/noah-l-frank/overte/blob/main/docs/PR_CI.md)
for selection and acceptance. Host-only changes do not provision Qt or produce
an IPA; selected application inputs retain the exact-source Qt/client handoff.

This is a personal hobby fork. Private signing/build configuration and Proxmox
Jenkins hardware jobs belong to the maintainer; host checks do not require that
setup. The retired workstation device lab is not a runtime-test fallback.

The retained platform recipes below describe build and diagnostic capabilities.
Their standalone routing and former qualification results do not replace the
central owner or establish that a hosted run occurred. Platform recipes include:

- `iOS bootstrap` (`.github/workflows/ios-bootstrap.yml`): Linux contracts,
  with explicitly selected simulator, device-SDK or integrated-client builds;
- `Provision Qt iOS source cache` (`.github/workflows/ios-qt-source.yml`): manual,
  or reusable preparation of matching Qt host and target trees;
- `iOS experimental integrated client gate`
  (`.github/workflows/ios-integrated.yml`): opt-in dependency, build, package,
  readiness, and sanitized-failure path; and
- `iOS device build qualification` (`.github/workflows/ios-build-qualification.yml`):
  exact PR merge-candidate routing, full physical-device client compilation and
  verified IPA provenance for changes targeting `apple-ios`.

Pushes to `apple-ios` and pull requests run the bootstrap workflow's Linux host
contracts when their changed files match its path filters. A green host result
does not establish that an IPA was produced.
Select `integrated=true` in a manual bootstrap dispatch to build the full
physical-device E2E client. Existing Qt, V8, Conan and compiler checkpoints are
restored through their validation paths; they do not substitute an older IPA.

## Build and installation evidence

The retained qualification recipe requires successful build jobs and compiler,
packaging and upload steps, then verifies the IPA against its exact source
revision, producing build number and SHA-256. Ordinary Markdown-only PRs take
an explicit lightweight route reporting `ipa: not-required`. That result does
not claim a compiled or installed application.

Keep workflow/run identity, source SHA and artifact digest with the installation
receipt. Build numbers belong to their producing workflow; app version `0.1.0`
or app build `1` alone does not identify the installed source. An unsigned IPA
still requires the separately authorized signing and installation process.
Successful installation does not establish physical-device acceptance.

Full-client E2E handoff artifacts have a one-day retention period. Other artifact
classes have their own retention settings; inspect the selected run's artifact
availability before installation. Follow the authoritative
[build qualification and provenance guide](../../IOS_BUILD_QUALIFICATION.md)
for prior-failure inspection, exact artifact validation and required-check rollout.

## Simulator scope

A manual bootstrap dispatch with no specialized mode selected runs the bootstrap
simulator and device-SDK jobs. `world_evidence=true` instead selects the explicit
Full Client simulator world-evidence path. Normal push and PR host checks do not
imply simulator execution. Markdown-only changes are excluded from `iOS bootstrap`;
the qualification workflow's lightweight result remains distinct from a device build.

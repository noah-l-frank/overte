---
last-reviewed: "2026-10-19"
scope: "Shared GitHub Actions design on main; platform callers retain their own requirements"
---

# GitHub Actions

GitHub Actions checks proposed repository changes. Jenkins owns the separately
configured device laboratory. A green pull request does not establish that a
physical device was tested.

## Required repository checks

The existing `repository-checks` aggregate evaluates the selected work. Routing
can choose documentation checks, bounded dependency-tool checks, or broader
host and native checks according to the actual candidate delta. See the
[project testing guide](../../../tests/PROJECT_TESTING.md) for prerequisites and
the [maintenance guide](../../REPOSITORY_MAINTENANCE.md#required-checks) for the
required-check design.

Synchronization may reuse qualified shared host evidence only for the exact
eligible source. Branch-owned tests and independent product gates retain their
requirements. A host qualification cannot replace a selected native result.

## Selected work and unchanged PR text edits

Selection uses the actual base and merge candidate, including deleted paths,
rename sources and file modes. A manifest or lockfile change belongs to its
package checks, dependency security checks, JavaScript build and behavior tests.
A change confined to `browser-client/package-lock.json` or
`script-archive/marketplace/S3Server/package-lock.json` does not select an
unrelated native Overte build. The S3 package does not select browser tests.
Browser application tests require changes to the corresponding browser client
inputs.

CodeQL selects the affected languages. Changes to shared security configuration
can require both supported language analyses, and scheduled scans retain their
full coverage. Workflow security has one mandatory PR owner; merging that same
change does not repeat the scan through a separate main-push owner.

A title or body edit with the same authenticated base, head and complete merge
tree retains the original mandatory results. If GitHub regenerates the temporary
merge commit, both immutable objects must also have the same ordered parents.
Its small read-only jobs must verify
the original successful Actions jobs before reporting `repository-checks` and
`codeql-security-results`. They run no new tests, builds or CodeQL analyses and
create no reusable execution evidence. A pending original is awaited; a failed,
missing or different original cannot become a passing result. A changed base or
head still requires selection and verification for the new candidate.

Synchronization has the same distinction between input selection and successful
execution. The required synchronization check owns the selected shared CI
contracts; independent Android and iOS owners remain mandatory when selected.
An unavailable optional parent receipt requires the applicable independent
checks, rather than an assumed reusable pass. A changed test controller may
invalidate a reviewed program identity and legitimately require a broader host
qualification. Inspect the recorded selection reason before interpreting a
full host job as an application build or a duplicate.

Compiler and dependency caches accelerate a relevant build; a cache hit is not
a passing test result. Cache-only CI changes must not start an application build
just to warm or measure the cache. Timing improvements require observations of
subsequent relevant builds and must not be inferred from configuration alone.

## Native builds

The [native lane guide](../../../tools/native-tests/README.md) owns routing,
dependency preparation, caches, and diagnostics. Relevant C++ or build changes
can select real production and native test targets; known documentation-only
changes skip product compilation.

The [qualification report](../../NATIVE_CI_QUALIFICATION.md) records the
September 27 activation on `main`, actual build costs, and a failing native test
that blocked a merge. Its timings and suite counts describe that revision.
They are historical measurements, not current latency guarantees.

## Inspect a run

Open [the fork's Actions page](https://github.com/noah-l-frank/overte/actions), select
the exact pull-request candidate or integrated commit, and inspect the failed
job before its aggregate. Match artifacts and reused evidence to that run and
revision. Distinguish a successful native job from a successful overall workflow.

Use the platform guides for Android and Apple build outputs. A verified APK or
IPA is build evidence; installed-app identity and physical behavior require
their own checks.

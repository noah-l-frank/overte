# Pull-request CI on main

The central pull-request workflow selects work once and observes the resulting
native GitHub Actions jobs. This guide describes that implementation. Installing
the source does not establish that its bootstrap passed or that branch rules have
been migrated. The initial rollout covers `main` only; the six platform branches
retain their existing rules until a separately verified migration.

## One context, one plan

[`repository-checks.yml`](../.github/workflows/repository-checks.yml) separates
candidate execution from acceptance:

1. The trusted controller authenticates the open pull request, repository,
   protected base, head, original merge commit, and complete merge tree.
2. [`pr_ci_plan.py`](../tools/repository-checks/pr_ci_plan.py) compares complete
   immutable base and candidate trees. It reads policy from the trusted controller
   and never imports candidate Python code to select work.
3. Selected owners execute their recorded commands. Candidate host and npm
   commands run in an isolated boundary without GitHub credentials, trusted
   controller mounts, or the host Docker socket. Dependency fetching is an
   explicit setup operation, not a fallback after a failed test.
4. The protected `pull_request_target` observer authenticates native jobs and the
   digest-bound execution record, rechecks the current PR, and reports
   `required-ci`. It never checks out or executes candidate code.

The original execution merge remains recorded even if GitHub later regenerates
an equivalent merge commit. Equivalence requires the same base, head, parent
geometry, and complete tree; a different tree cannot borrow an earlier result.

The active suite and dependency definitions are
[`pr-ci-suites.json`](../.github/pr-ci-suites.json) and
[`pr-ci-dependencies.json`](../.github/pr-ci-dependencies.json). Historical
registries, workflow-generation catalogs, and the combined profiles in
[`PROJECT_TESTING.md`](../tests/PROJECT_TESTING.md) remain available to their
existing readers. They do not define the new main profile.

## Select the consumer that changed

Every task has a unique ID, explicit commands, input closure, and setup needs.
Unknown or non-ordinary inputs select conservative coverage. Deletions and
renames participate in the full tree comparison.

| Changed input | Required consumer work |
| --- | --- |
| Central CI code, policy, or workflow recipes | Applicable planner, context, runner, observer, transport, CLI, workflow, and security contracts |
| Product source | Host contracts and native or platform owners selected from their actual inputs |
| S3 uploader lockfile | Its npm install, audit, and tests; no browser journey or native C++ build |
| Browser package manifests or lockfiles | npm install, audit, and consumer build/tests; no unchanged browser journey |
| Verified compatible Vite patch only | Build the affected consumer; the browser client also runs its existing Vite-built FBX worker test, and the direct client retains its npm tests |
| JSDoc package inputs | npm install, audit, and actual JSDoc generation into a temporary output directory |
| Verified Pillow 13 requirement update only | The 32 image-observation units and one animated-overlay Qt regression; no complete Overte build |
| Other Python requirement or dependency-graph changes | Conservative consumer coverage rather than the bounded dependency profile |
| Documentation inputs | Documentation contracts; these also inspect link targets and source declarations |

The Vite profile checks the complete manifest and lock graph complements,
scripts, configuration, and consumer source inputs. Source changes or an unknown
graph change keep the full package profile. The Pillow profile requires the exact
reviewed requirement change and unchanged remaining requirement bytes. The Qt
regression is a small host contract, not a device or full application build.

Package tasks remain selected in mixed source/dependency changes. Server-console
testing includes its packager version check. Its registered standalone Node test
may be covered by `npm test` only when the script is that exact command, has no
pre/post hooks, and all ordinary registered inputs are present. The plan retains
that logical coverage instead of running the same command twice.

CodeQL selects the actual Python or JavaScript/TypeScript extractor footprint.
The trusted central analysis recipe and configuration govern the selection;
changing those controls requires both analyses. Reviewed npm-lock exclusions
leave dependency security to npm audit. An unknown analysis configuration fails
closed. Pending SARIF processing or an unverified upload is never success.

Task fingerprints include input modes and blobs, commands, setup, and trusted
runtime inputs. Content-scoped host tasks omit an unrelated target branch;
candidate-scoped tasks retain it. A fingerprint is a comparison key, not a test
result, reusable evidence, or permission to skip a required owner.

## Activate main without weakening its rules

Before changing required checks, an authorized maintainer must run the manual
`Repository checks` bootstrap on the exact reviewed PR head, supplying its real
`pr_number`. The manual controller must equal that head. The bootstrap must finish
with genuine selected-owner success, authenticated execution transport, complete
CodeQL processing when selected, and unchanged PR identities.

Only after that result is verified should the existing main requirements be
replaced by the protected native `required-ci` check. Keep the old requirements
until this transition is justified; never replace missing results with synthetic
checks, administrative bypasses, or a success from another head. Finalize the PR
description before the qualification run when possible. Text-only edits observe
existing genuine execution rather than starting another set of owners.

The controlled rollout also needs these automation changes:

- Remove `main` from the old Parent qualification, Documentation checks, and
  Dependency release policy **push** triggers, and from Sync test reuse's
  `pull_request_target` trigger. The new PR plan owns main's corresponding work.
- Hold automatic branch-cleanup writes on closed-PR, scheduled, and completion
  events during the transition. That workflow can create history-integration PRs
  and retire integrated branches. Retain its explicit read-only report mode.
- Keep Branch synchronization's read-only drift report. It does not create or
  merge child PRs. Scheduled dependency inventories and security scans remain
  distinct maintenance work.

The new central workflow has no main push trigger. Its acceptance does not need
a duplicate post-merge host run. Existing child push owners and product build
workflows are not implicitly retired by the main transition.

Do not propagate the new controller into child PRs under an assumption that old
default-branch helpers enroll it automatically. Their requirement-source,
controller/import, and complete workflow-tuple checks deliberately reject an
unreviewed combination. A main-only workflow also cannot supply a child's legacy
required check. Hold that propagation until its target-specific routing and
required-check transition have been tested; do not add a catalog generation just
to disguise the mismatch.

## Check a focused local change

Run the contracts for the files changed, using the supported Python environment:

```bash
python3 -B tests/pr-ci-plan-test.py
python3 -B tests/pr-ci-context-test.py
python3 -B tests/pr-ci-run-test.py
python3 -B tests/pr-ci-observer-test.py
python3 -B tests/pr-ci-transport-test.py
python3 -B tests/pr-ci-cli-test.py
python3 -B tests/pr-ci-workflow-test.py
git diff --check
```

These commands test selection, isolation, and acceptance contracts. They do not
dispatch Actions, compile the complete application, or establish device
acceptance. Report local checks, prospective input selection, native execution,
and device evidence separately. GitHub changes belong only in
`noah-l-frank/overte`; follow the existing branch and contribution policies.

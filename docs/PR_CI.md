# Selective pull-request CI

The central pull-request workflow selects work once and observes the resulting
native GitHub Actions jobs. This guide describes that implementation. Installing
the source does not establish that its bootstrap passed or that branch rules have
been migrated. The source routing covers all seven protected branches. The same trusted
controller owns policy, shared host tests, packages, native C++, CodeQL and
selected Android/iOS contracts. GitHub Actions remains disabled under the
maintainer's local-only integration instruction; installing these sources does
not claim a hosted execution or physical-device qualification.

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
4. A short protected `pull_request_target` job reports `source-policy` after
   authenticating the complete workflow and controller inventory. It never
   checks out or executes candidate code. The native `required-ci` job starts
   after selected execution owners finish, authenticates their native jobs and
   digest-bound execution record, and rechecks the current PR. Both contexts
   are required. Metadata-only runs cannot publish a replacement `required-ci`.

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

Host and npm execution now publish separate task receipts. For a direct
parent-to-child propagation, the controller can reuse the original successful
command only after authenticating its repository, owning ancestor, merged PR,
tested/integrated tree, workflow and controller sources, native run/attempt,
check-suite application, required jobs, artifact digest and original command.
Input keys and actual mounted tool/package runtime fingerprints must match.
The final merge gate independently reauthenticates each reused command. An
origin remains the original executed command across multiple propagation edges.
Missing, expired or incompatible optional evidence causes execution without
polling or requesting another run. npm installation and vulnerability queries
still execute; mutable advisory data is never reused as an immutable result.

Runtime fingerprints include the actual OS/runner image, installed packages,
Python and prepared tool bytes. Relocating an equivalent prepared tool bundle
does not by itself invalidate it. A kernel, package or tool change does.
Native/compiler caches and platform host fallbacks remain conservative; they
are not promoted to successful test evidence by a matching cache key.

Before publication, inspect local immutable inputs without contacting GitHub:

```sh
python3 -I -S -B tools/repository-checks/pr_ci.py preflight \
    --candidate . --base origin/main --revision HEAD --target main --out preflight.json
```

Use the actual target and its base ref. This reports selection and known
platform prerequisites; it never issues execution or merge authority. Android
production native/build changes currently require the separately qualified
source-only dependency graph and hosted target consumer described in
[platform coverage](PR_CI_PLATFORM_COVERAGE.md). Their prerequisite check runs
before expensive selected owners and blocks acceptance when that environment
is unavailable. Java/resource compilation is a distinct verified tier, not an
APK or native-build claim.

The preflight also reports incompatible workflow/controller sources before a PR
is published. `--allow-controller-transition` is only for the explicitly
reviewed local rollout procedure while Actions are disabled; it cannot bypass
the protected GitHub source policy or waive missing Android prerequisites.

## Platform ownership and merge gates

All seven targets require the same `source-policy` and `required-ci` contexts. Branch-path guards retain
their separate topology checks. The previous shared PR, synchronization and
post-merge push producers are retired so an integrated PR does not repeat its
host, package or CodeQL work. Explicit diagnostics, release jobs and maintenance
schedules remain separate from PR acceptance.

The Android owner executes the branch's complete reviewed platform inventory
from [pr-ci-platforms.json](../.github/pr-ci-platforms.json). A candidate cannot
remove a mandatory suite by editing its own profile. Commands run inside the
same offline, credential-free namespace used by shared host tests.

The selected iOS owner runs the actual iOS host contracts. Host-only inputs do
not provision Qt or build an IPA. Application inputs additionally select the
existing Qt and full-client recipes exactly once, preserving their audited
compiler caches. The client consumes the successful same-source host handoff
instead of repeating that launcher. The final owner checks actual compile,
package and upload steps and the exact source-bound IPA. No device tests run as
part of this host/build owner; device acceptance belongs to the Proxmox Jenkins
laboratory.

Unchanged product workflows already installed on a protected child may retain
their branch implementation. This exception uses the independently read
protected base and cannot authorize a PR to add, modify or delete a workflow.
Central executors, reusable build recipes, helpers and policy must match the
protected default-branch controller exactly.

The maintainer explicitly authorized local verification followed by direct
integration while Actions is disabled. This is a scoped integration exception,
not a reusable passing check. No synthetic status or hosted test result is
created. Enabling Actions later requires an explicit maintainer instruction;
source readiness and local results must not be described as hosted success.

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
python3 -B tests/pr-ci-platform-test.py
git diff --check
```

These commands test selection, isolation, and acceptance contracts. They do not
dispatch Actions, compile the complete application, or establish device
acceptance. Report local checks, prospective input selection, native execution,
and device evidence separately. GitHub changes belong only in
`noah-l-frank/overte`; follow the existing branch and contribution policies.

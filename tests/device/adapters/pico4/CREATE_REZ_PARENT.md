# Pico Create Runner rez ownership and actual client rights

Feature 4/14 remains **partial**. The existing v16 parent now composes both
`set-rez-permission` steps and exact original rights restoration during joint
cleanup. Permission denial/retry input, independent peer facts, actual stereo
render/pixels/artifacts and complete resource retirement remain separate work.
No full `feature.create.*` capability is advertised by this source package.

## Fixed Phone reuse and authority

The common `fixture/create_permissions.py` and its eight original host tests are
copied unchanged from read-only Phone source
`5527d540e99cc6dba4204a5e904a854e6e1cd2b4`; the original implementation was
introduced by `8f77da49538d64c3dd35332f251ceea01e21ba7f`.
Pico's small subclass retains the original process PID/start/owned-process,
domain UUID, normal Settings API, private CAS and outside-security hash checks.
It admits only complete typed original `NodePermissions::toVariant` standard
rows and empty override lists, so unsupported columns cannot disappear during
normal serialization. After the durable intent, a fresh original read compares
all standard rows and outside-security hash again immediately before the normal
POST; a foreign non-rez field changed during that CAS prevents every Settings
write and retains its pending owner. No client permission setter or reconnect is introduced.

The subclass tightens uncertain POST recovery: a still-original Settings row is
unknown completion, so its exact pending owner remains. Reconstructing and
observing, setting or restoring cannot resend the uncertain request. Only the
actual pending target can recover read-only. A successful HTTP ACK alone proves
no Settings or client effect. Original acquisition uses both host monotonic and
producer epoch admission, retaining the original beginning epoch; a frozen
producer epoch cannot hide a two-second acquisition. The original HTTP inactivity
limit remains two seconds and responses remain bounded to one MiB.

The domain fixture enables this only with the new explicit
`--feature-pico-create-permissions` flag. Its original initial config reserves
four ordinary standard classes and empty override lists. Its actual owned
normal `/settings.json` endpoint handles all changes. The private ready file
adds only `createPermissionsControlUrl`, sharing the original loopback controller
origin and control credential. The existing default fixture has no new row or
endpoint authority. A live permission lease prevents ordinary fixture restart;
shutdown preserves an unresolved private journal instead of claiming restoration.

## Runner phase and adapter read path

The existing feature server optionally accepts a private
`createPermissionProvider` configuration with exactly `controlUrl`,
`controlToken`, `domainId`, and absolute private `stateFile`. The URL must be the
original `http://127.0.0.1:<port>/v1/create-permissions`. The provider reserves one
run and opaque owner durably before its first domain request. A lost initial
snapshot leaves an explicitly unknown reservation; neither an empty baseline nor
a different run may adopt it. It never provisions another grant on recovery.

Original runner registration acquires the four original typed rows. Only the
existing authenticated runner activation of the closed v16
`set-rez-permission` stimulus can change their two rez bits. The exact original
Journal activation precedes the durable provider intent and original request.
`cleanup` activation restores the original rows, including individually different
original temporary-rez bits. A lost response keeps its exact pending activation;
a read may recover only the actual target, with no request replay. Runner close
requires actual original readback and successful retirement of the original
controller's private journal. Provider errors retain ownership and return a
closed unavailable response, not an internal-success acknowledgment.

The adapter receives only GET
`/feature-fixture/v1/runs/<run>/create-permissions`, with a fresh
`X-Overte-Phase-Read` nonce. Its separate existing credential remains incapable
of POST, phase activation, deletion or peer publication. The public source
contains original typed rows, actual Settings readback, immutable original
activation receipts and exact phase instance/history. It contains no owner or
control credential and supplies no client permission or product verdict.

## Existing Pico parent composition

The existing parent durably retains this additional side owner under its same
candidate/run/source lock, without replacing any previous source histories.
The actual native entity getter remains a separate original rights source.
The original parent call becomes pending before any Settings readback can fail.
A lost first read therefore blocks every subsequent act; same-ticket recovery is
read-only, while an advanced original phase retains the original pending call.
The parent checks original domain/process/scene/connection-generation identity
and surrounding exact phase history; original baseline packets are not edited
or retimed to permit a rights transition. Existing child scene comparisons keep
their original strict rights equality. The parent alone admits the joined
controlled transition, requiring actual native `canRez` and `canRezTmp` to equal
its independently read target before completing a step or granting another
normal input. Unknown mixed rights remain invalid.

A quiet completion requires three seconds of advancing actual entity, original
Settings and original Script-work clocks, plus host monotonic time. Each effect
retains the exact actual native packet bytes and SHA, original Settings packet,
and original ticket. Later settings reads and cold reconstruction cannot erase
or relabel the earlier denial observation. The existing final phase/sample/CAS
freshness checks also cover the original Settings timestamp. Joint cleanup first
observes actual original Settings and native rights before child/resource/UI
cleanup and before discarding the parent's side owner.

These prove original API rows and native client rights at the stated boundaries.
They do not independently read the physical domain INI/JSON file and do not
qualify exact persisted configuration bytes, DomainServer execution, a real
networked Interface or peer behavior. Those claims are not inferred from ACKs.

## Host qualification and combined profile boundary

`create-rez-permissions` runs the strict subclass's inherited fixed Phone cases
and Pico counterexamples with actual private CAS and short-lived owned loopback
HTTP. Only the Settings/domain worker is synthetic. It exercises the actual
DomainControlHandler, feature server, runner role, original Journal activation
and separate GET-only adapter role. `create-rez-owner` joins those same actual
components through the existing Pico parent and original native readers; native
permissions/domain/UI remain explicitly declared actors. Settings without actual
client effect keep the original parent pending, send no UI and never resend a
Settings write; later real actor effect reconciles without replay.

The local catalog adds two bounded selectors (70 to 72); integration must add
them to the parent's actual current catalog and preserve newer groups. Four new
private version-1 contracts are registered: `pico-create-rez-controller`,
`pico-create-rez-provider`, `pico-create-rez-source`, `pico-create-rez-owner`.
Existing journey v16 and Create parent v3 schemas remain supported unchanged.

The fixed newer Chat `OwnedChatMixer` reader at
`80133a643757ef328d838e663088320a5b922185` initially requires an exact ready-file
field set without the new optional Create URL. Until its separately reviewed
optional same-origin URL admission and counterexamples are integrated, run the
Create and Chat opt-in profiles separately. This package does not copy moving
Chat work or claim that combined profile is qualified.

Validation for this packet, with `PYTHONDONTWRITEBYTECODE=1` and the owned private
TMPDIR, without inherited PYTHONPATH or device access:

- `python3 android/vr/pico/tests/pico4-test-suite.py --test create-rez-permissions --test create-rez-owner --test coverage-matrix`: 3/72 groups passed in 34.95 seconds; strict Settings 16 cases in 10.948 seconds, four parent cases in 23.948 seconds.
- `python3 tests/device/self_tests/test_create_permissions.py`: all eight unchanged original Phone foundation cases passed in 4.351 seconds. Both copied files match their exact pinned Git blob IDs.
- Existing separate adapter-role tests and the domain fixture's dry contract check: 12 cases passed in 6.229 seconds.
- Contract registry, exact generated v16 inventory, all 578 Markdown documents and whitespace checks passed. Timeouts, assertions and existing selectors were preserved.

There were no physical Pico/OpenXR runs, actual DomainServer/Assignment Client
runs, complete Interface builds, remote writes or changes to a Phone worktree.

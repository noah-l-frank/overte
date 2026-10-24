# Controlled E2E domain fixture

`domain.py` owns a private, ephemeral domain-server, one assignment-client
monitor, and repository-owned content and controlled-peer assignments. The
content assignment creates four uniquely named domain entities; the peer
assignment publishes one deterministic moving avatar. The common
`domain-smoke` module requires a real domain connection,
the exact domain UUID returned by `/id`, all four markers for consecutive probe
samples, stable process identity, and foreground state.

Run it only with locally built, trusted executables and keep its output outside
the checkout:

```bash
python3 tests/device/fixture/domain.py \
  --domain-server /absolute/build/domain-server \
  --assignment-client /absolute/build/assignment-client \
  --public-host 192.0.2.10 \
  --output-dir /tmp/overte-domain-fixture \
  --ready-file /tmp/overte-domain-ready.json
```

The ready file supplies `domainUrl`, `domainHost`, `domainId`, and
`requiredMarkers`. Export those values as `OVERTE_E2E_DOMAIN_URL`,
`OVERTE_E2E_DOMAIN_HOST`, `OVERTE_E2E_DOMAIN_ID`, and
`OVERTE_E2E_DOMAIN_MARKERS_JSON` before running `domain-smoke`.

It also supplies `peerScriptUrl`, `peerDisplayName`, and a loopback-only
`controlUrl` plus random `controlToken`. The token exists only in the mode-0600
ready file and is omitted from stdout. `network-fault-recovery` exports those
last two values as `OVERTE_E2E_DOMAIN_CONTROL_URL` and
`OVERTE_E2E_DOMAIN_CONTROL_TOKEN`. Its `offline` and `online` commands affect
only child process groups owned by this fixture instance.

Before each `enter_controlled_domain()` navigation, sessions with either private
control value request `online`; both values must be valid together. The existing
owner checks its live domain and assignment children plus the current `/id` when
already online, or starts its stopped owned stack and waits for assignment
content. A healthy stack is not restarted. A stale ready file is insufficient.
`domain-prerequisite.json` records state/generation without the private token.
An unavailable, invalid or foreign-identity owner blocks navigation as an
infrastructure error before adapter input. External/mock sessions with neither
control value retain their externally managed lifecycle. This process/identity
check supplies no client arrival, grounded-pose or rendered-world verdict.
The manifest's actual `spawnPath` keeps feet on the known y=0 floor; do not
replace it with a raised camera-height address.

`domain-recovery` uses the same values plus `OVERTE_E2E_SCENE_URL`. It enters
the domain, returns to the controlled serverless scene, proves that the domain
is disconnected, and re-enters the exact domain without changing the
Interface process identity.

The controller's ready metadata means only that the infrastructure is
reachable and its assignment processes survived warmup. Only the client probe
can prove that the domain handshake completed and the entity server delivered
the assignment-owned markers. Each product adapter advertises
`navigation.enter-domain` only after its own physical acceptance gate.

## Optional failure hold for laboratory diagnosis

The default controller still cleans up its owned stack on failure. On Linux,
`--debug-hold-on-error` instead preserves failed startup or runtime state after
its private output owner has been established. It does not restart a worker or
resume the test. The controller records each registered child's original
PID/birth/role and its actual failure-time `Popen.poll()` return code in
`output/debug-hold/FAILURE.private.json`. A setup failure can legitimately have
zero registered children. No device or feature qualification follows from these
host observations.

A held failure rejects control GET and POST requests with HTTP 503. Current
READY is withdrawn, while its original content is retained privately as
`debug-hold/READY_BEFORE_FAILURE.private.json` when one had been published.
Independent live-owner/child/source checks must still reject the failed stack;
a historical READY file cannot replace those checks. Logs and surviving owned
children remain available for diagnosis. Ordinary SIGTERM/SIGINT does not release
this intentional hold. SIGKILL cannot be prevented and supplies no cleanup proof.

The only release action is cleanup. The exact controller's live owner must
publish a mode-0600 regular, non-symlink file at
`output/debug-hold/RELEASE_REQUEST.private.json`, using the actual context digest
and nonce from the same mode-0600 `OWNER.private.json`:

```json
{"schemaVersion":1,"action":"cleanup","contextSha256":"<actual owner context SHA256>","nonce":"<actual owner nonce>"}
```

Directories are mode 0700. Keep the nonce, READY tokens and full native logs
private. Foreign context, nonce, permissions, duplicate JSON keys or aliases do
not authorize cleanup. An accepted request produces
`RELEASE_ACCEPTED.private.json`, then the existing owned cleanup runs and the
original failure is re-raised. Release never turns a failed run into PASS.
Recording or release-validation errors retain the hold rather than treating
uncertain evidence as cleanup authorization. Invalid arguments/output ownership
before the private owner exists cannot create a valid hold.

A future pinned native launcher must explicitly admit this changed controller
source and the opt-in flag. This option does not alter an older deployed
controller, restore already-retired processes or retroactively preserve a
historical failure.

### Optional owned-cgroup memory guard

With debug hold enabled, `--debug-memory-expected-limit-bytes N` also opts in
host-only memory sampling. `N` must equal the actual own container budget's finite
`memory.max`. The controller joins `/proc/self/cgroup` with the actual cgroup2
mount root and proves its direct task-leaf PID membership in `cgroup.procs`.
An unbounded task leaf may charge a finite parent budget; only ancestors within
the kernel's own libpod container scope and actual mount root are considered.
The effective finite budget must match `N`; host-global fallback is forbidden. The launcher separately pins the authorized
container RAM and swap limits. Changing this argument never changes a limit.

`debug-hold/MEMORY_TIMELINE.private.jsonl` records a pre-launch sample and
approximately one sample per second during startup and the active fixture:
actual current/max/peak bytes, event counters, actual own-process RSS and
identity, and host observation times. The rows are not atomic native frames or
client measurements. The file is private mode0600 and bounded to8MiB. It stops
appending when failure hold begins; the immutable failure receipt retains the
triggering sample and freeze result. Full native logs are also created
exclusively with explicit mode0600 when debug hold is enabled.

The authored headroom reserve is `max(256MiB, floor(actual memory.max / 10))`.
At or above `memory.max - reserve`, the controller first pauses only its proven
owned native process-group members with pidfd-bound SIGSTOP, then records the
failed infrastructure state. Birth, UID, process group and cgroup must still
match before any signal; group membership is checked again after stopping.
The controller remains alive for diagnosis. This is an ERROR, not a successful
test or evidence of a particular allocation leak. Sampling cannot guarantee
that an unbounded allocation burst will be caught before the kernel's limit.

An exact cleanup release revalidates and SIGCONT-resumes only those same pinned
members, so the original TERM-based cleanup can retire them. No worker is
restarted. No OOM-score, global memory policy or unrelated process is changed.
A rejected ownership check keeps the failure explicit and supplies no claim
that every allocation source was successfully paused.

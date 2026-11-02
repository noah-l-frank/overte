# Create peer CLI v5 and the original persistent Parent

Feature 4/14 remains partial. `feature_observer.py --config <private-file>` now
has a version-5 `create` route through `PicoCreatePeerWorker`. The factory reuses
the existing installed-candidate/native guards, `_script_runtime`, actual UI
bridge binding, Create entity/resource readers, fixture phase reader and source
lock. It does not launch/repair an application, discover a target, submit normal
input, change permissions or start a Domain/service. This is the existing
[native Model peer component](CREATE_INDEPENDENT_MODEL_PEER.md), not the complete
common Create Actor.

## Necessary process and coordinator ownership

The original Parent must be a persistent warm host process. The worker must be
its actual direct OS child: admission checks `getppid()` against the original
Parent PID, and the Parent obtains its zero exit status with actual `waitpid`.
An independently launched Jenkins sibling cannot supply this authority.
Short-lived adapter RPCs that exit after `issue_peer_scope()` cannot own this
workflow. Kernel ESRCH alone, an exit-looking JSON value or a successful nonce
echo cannot replace the kernel zero-exit result.

After full immutable ready publication and its final guards, the child emits
the single fixed stdout line `OVT_PICO_CREATE_PEER_RETURN_READY`. The warm
coordinator can then construct the actual receiver from that child's original
transport. This local notification contains no target, token or effect facts;
it is not a completion receipt. The receiver still checks every original byte
and the Parent still needs consumed nonce, terminal outcome and kernel status.
No polling race on the transport's intermediate `reading` writes is excused.

No persistent adapter backend or Jenkins job/launcher is added here. An already
authorized Proxmox warm coordinator must create the child with the reviewed
entrypoint/interpreter, acquire the existing `LinuxChatObserverProcess` while it
is live, preserve that original owner, and use `accept_peer_return()` before
reaping it elsewhere. All actual device access stays in the Proxmox USB lab;
the workstation must never run this route against a device. The source package
does not claim that a current Jenkins job meets this warm-Parent prerequisite.

The same coordinator must enter
`parent.peer_input_boundary(config_path, original_worker_owner)` **before**
publishing a new fixture ticket, and hold it across the ordinary Parent input.
This uses the worker's actual `ScriptSourceLock` so native originals cannot be
acquired under one ticket and completed after the next ticket. It supplies no
effect facts. A phase crossed during an issued acquisition still fails sticky.
Only genuine lock contention before any new acquisition may wait; waiting keeps
the same original config deadline and sends no query. Provider activation and
input must not happen outside this boundary in the continuous composition.

## Private configuration and admission

The version-5 config preserves the existing base fields:
`picoFeatureObserverVersion`, `area`, `target`, `candidateArguments`,
`fixtureUrl`, `actorToken`, and `durationSeconds`. It additionally requires:

- `artifactRoot`: an existing canonical private directory for a new worker.
- `peerOwner`: the exact original issued Parent companion's absolute path.
- `peerOwnerSha256`, `peerOwnerStamp`: full original bytes/hash and all eight
  physical fields from that issued file, not a copied scope-only DTO.
- `runId`, `originalRequestId`: the original run and scope request.
- `workerExecutableSha256`, `workerEntrySha256`: the selected actual Python
  executable and reviewed entrypoint hashes.

No extra runner credential, effect verdict, requested entity/type, startup
action or repair instruction is admitted. The existing candidate CLI is used
only as `describe` for the exact selected Pico target; its native binding/kind,
operation and arguments are checked before the adapter is constructed. The
actor token is only used for existing read-only phase queries by this component.

Before candidate construction, `CreatePeerAdmission` holds the original config
and issued-owner files and directories through `ChatArchiveCatalog`. Every
control verifies the original OFDs, fresh canonical parent identity, complete
physical stamps and full bytes. `LinuxChatObserverProcess` qualifies the actual
current worker executable, entrypoint, config and exact `--config` cmdline.
Changing the config even to identical replacement bytes refuses its old owner.

An exclusive `create-peer-worker-claim-<request>.json` is created beside the
issued Parent companion after program admission. It records the one original
host identity, config/issued-source hashes and beginning/deadline. Failure does
not remove or adopt this claim. A new process, new artifact directory or repeated
config cannot renew that issued scope's worker deadline. The original private
claim remains evidence; no cold repair/restart route is introduced.

The original monotonic deadline includes candidate acquisition, all controls,
queries, actual input-boundary waiting, return construction, nonce waiting,
consumption and closure. Clock regressions refuse. No waiting loop resets it,
extends query limits or increases the common 120-second journey budget.

## Return v2, terminal outcome and historical acceptance

Standalone native component return v1 remains readable and keeps its existing
format. CLI workers produce return v2 with an additional typed worker proof.
That proof names the guarded `create-peer-worker.json` journal and immutable
worker/config/issued-scope/program identity. The worker journal progresses
through acquisition, observation, return-ready, consumption, closure and failure.
It uses the existing `LifecycleProcessFile` original OFD/CAS writer.

Return bytes still use the unchanged `ObserverReturnSender` and receiver. The
Parent revalidates the original config, exclusive claim, source originals,
worker journal, native quiet proof, exact provider and actual program owner.
After the original consumed echo it additionally requires a closed journal,
actual kernel zero exit of that same direct child, and completion observed
before that worker's original deadline. A timeout/refusal after writing the
echo remains unresolved. Even a deliberately closed-looking marker from a
process that actually exits nonzero is refused.

Successful CLI acceptance writes Parent companion v2 with a separate immutable
acceptance event; v1 histories remain readable. This retains the original
transport receipt and exact kernel status rather than rewriting them into a
success flag. Later Parent cleanup validates this historical acceptance against
the same original worker/config/claim files and complete native source history.
It does not re-query a dead PID or renew the old deadline. The Parent still
requires its own unchanged complete three-second multi-source quiet window.
Worker source/claim/config/return files remain retained evidence; their final
global archive remains separate work.

## Host proof boundaries

`CreatePeerCliTests` run the actual production configuration parser, main,
Create factory, continuous loop and Parent acceptance in a distinct real child
process. Only candidate/SDK, Native/Qt, replica/renderer, fixture and time
producers are explicit models. Actual private files, OFDs, executable/entry
ownership, provider/input locking, nonce transport, kernel child status, actual
absence and original Parent normal controls execute. No socket, device, service,
build, compiler, Domain or remote write is activated.

The original stdin fixture is reused for native replica/resource production.
The continuous mode requires an explicit replica fixture lock and a real
Parent input boundary; it must not be made reliable by swallowing the
production source's atomic-replacement or crossed-phase refusals. Those actual
failure runs and all originals remain retained outside the repository.

Real SDK/ADB acquisition latency, second Pico client availability, actual
rendering/permissions/PolyVox/UI Actor facts, texture bytes/GPU/stereo, persistent
coordinator/job integration and final global archive/device acceptance remain
open. A successful host model run does not qualify any of these boundaries.

## Scoped validation (2026-11-03)

The final eight-case owning group passed in 52.761 seconds with the loaded
source set unchanged (235 local files). It includes actual production main/factory/loop, normal
Parent Open/NEW/Delete/cleanup, v2 return, real nonce and direct-child kernel
status. The independent three-second proof remains mandatory. The contention
counter holds the real source lock for 5.3 seconds and proves no query or source
file change, no config beginning/deadline renewal, and subsequent original
cleanup. The two after-written-echo counters preserve failed/expired worker
ownership; a false closed marker plus an actual nonzero child exit refuses.

Earlier seven-case runs failed on the host fixture's concurrent atomic file
replacement (47.621 seconds) and, after fixture synchronization, correctly
refused a crossed original fixture phase (18.760 seconds). The source refusal
was preserved; the real Parent input boundary addressed the missing coordinator
join. The first boundary group passed eight cases in 77.541 seconds before the
explicit publication notification. These times do not establish a production
throughput improvement. Original failures, source/pending records, executable
ownership and unchanged-source manifests remain outside the repository.

The initial one-case chain passed in 10.133 seconds as a bootstrap diagnostic;
it was not the final scoped source-freeze result. The final owning evidence is
`/home/user/.local/state/pico-create-cli-final-20261103-p79i5ziu`.
The existing standalone v1 source/Parent group also passed all eleven cases in
40.218 seconds, with 231 loaded local source hashes unchanged. The existing
authentication/graphics/Chat observer compatibility group passed twelve cases
in 0.043 seconds with 145 hashes unchanged. No unchanged whole journey or native
compiler group was repeated.

Schema details for integration: `picoFeatureObserverVersion` is current 5,
reading 1–5; `createPeerReturnVersion` is current 2, reading 1/2. Standalone
native senders continue writing original v1; only CLI writers add v2's worker
proof. `createPeerParentVersion` reads 1/2: issued/v1 component histories retain
their v1 format, while successful CLI acceptance writes v2 with
`workerAcceptance`. The source and ownership-scope DTOs remain v1. New worker,
exclusive claim, worker proof and nested acceptance records are each version 1
(`createPeerWorkerVersion`, `createPeerWorkerClaimVersion`,
`createPeerWorkerProofVersion`, `createPeerWorkerAcceptanceVersion`). Registry
and catalog integration is owned separately; no complete capability is implied.

## Fixed Phone Create reuse audit

The later read-only Phone tip
`5e8ff8aa19571f5718b982dc47a165b8f22e0dc0` descends from the previously selected
`a7be274da152b9d0b77e2fe5bb9874c5b1e18a31`. All thirteen
`overte_phone_create_*.py` runtime modules are byte-identical between these two
fixed revisions; exact per-file hashes are retained in the external
`fixed-phone-create-audit.json`. This statement concerns these runtime modules,
not every Phone document or shared/native dependency.

The complete Phone Feature/Actor/Role/Retirement/Evidence composition was
reviewed as architecture. Its Actor waits for acknowledged Primary actions under
the shared Feature lock and acquires new native/UI/image originals. Its Role
queries that Feature's selector and requires the same stored binding. That is
independent-host/same-client evidence; it cannot replace this Pico component's
required distinct native client/session. Its retirement accepts changed PID
start or zombie state, and its Actor quiet helper permits 1.5-second gaps. These
predicates are not imported over Pico's actual zero-exit/ESRCH and 500-millisecond
requirements.

Phone's native render/texture/cell DTO, touch/input and Mono pixel dependencies
also differ from the current Pico sources. The reusable ordering is original
input barrier, independently reacquired facts, immutable original archive,
retained failed ownership and final original cleanup. Existing Pico owners and
shared source/process/return engines supply those primitives here. No Phone
module, touch/Mono assertion, Common-version migration or weaker predicate is
copied into this packet. Phone's source-composition status does not qualify the
Pico actor or either platform on devices.

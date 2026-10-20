# Owned MessagesMixer control v1

The existing domain fixture now exposes a mixer-only process actuator on Linux.
It implements a controlled failure input, not a complete Chat adapter or a peer
receipt. No actual Overte domain/mixer, device, build or Jenkins job was run.
Its host checks use synthetic Python processes and loopback HTTP only.

## Scope and source

`Assignment::MessagesMixerType` is type 4, distinct from AvatarMixer (1), Agent
(2), AssetServer (3), EntityScriptServer (5) and EntityServer (6). The fixture
already starts one dedicated process for each type. Only that original type-4
process is eligible for this actuator. The domain server, all other services,
assignment Agents and tested client remain alive throughout a mixer outage.
Do not substitute whole-domain offline/online, a dropped HTTP connection or a
requested boolean for actual MessagesMixer loss.

The owned service is restarted through the same reviewed fixture command for
`-t 4`, with its existing private environment/config/domain address. No pool,
Chat actor subscription or `--testScript` flag is permitted on this process.
On a lost static assignment, the original
`DomainServer::refreshStaticAssignmentAndAddToQueue` resets its UUID before
requeueing it. Therefore recovery must observe a fresh native mixer identity;
matching old cached identities after both native readers saw absence are not
recovery. `IndependentChatReceiver` now explicitly rejects that counterexample.
Source review is not a claim about installed code or network timing.

## Closed endpoint and observations

With the existing explicit `--feature-chat-receiver` fixture opt-in, the private
ready file adds `messagesMixerControlUrl`, an owned loopback
`/v1/messages-mixer-state` endpoint. Both GET and POST require the existing
`X-Overte-E2E-Token`; no credential is printed or exposed to public scripts.
Unsupported hosts or an unavailable/offline owning domain return unavailable.

POST accepts exactly `{schemaVersion:1, action:"offline"|"online"}`. The integer
version is not a boolean; extra expected-node/result fields and unrelated service
or whole-stack commands are rejected. GET applies no input. Each successful
response has exactly:

```
{mixerProcessVersion:1, running:<boolean>, generation:<positive integer>,
 pending:<boolean>}
```

`running` is qualified actual process state. It is **not** a native-node presence,
subscription acknowledgement, readiness, connection, UI or delivery fact.
`generation` advances after actual owned stop/start, not repeated requests.
`pending` includes original unresolved intent; an ignored journal removal cannot
produce a completed receipt. PID/start and owner material remain private.

`fixture.messages_mixer.MessagesMixer` requires an already-owned actual Popen,
actual fixture ownership callback, owned spawn callback and independent private
intent write/read/removal callbacks. It pins the original Linux kernel starttime
and verifies actual owner environment and typed argv. Normal state reads query
those sources again. A bounded one-second read retry handles a shebang launcher's
transient exec window while retaining the exact child/start. It never adopts a
new PID, foreign owner, wrong assignment type or a requested target state.
Production use must bind the configured actual executable to the reviewed fixture
artifact/source; process existence alone does not qualify a feature verdict.

Before input persist the original process/start/action intent to the fixture's
0600 `messages-mixer-intent.json` and independently read it back. An ignored or
failed persistence ACK cannot permit signalling/spawning. Stop pins the actual
PID with a pidfd, rechecks original start/owner/type and sends SIGTERM to that
exact process, waiting at most two seconds; SIGKILL on the same pidfd gets a
further two seconds. It requires actual Popen exit and freshly checks original
kernel-process absence for subsequent offline receipts. A reused foreign PID
cannot retarget the signal or become the original stopped mixer.

Start retains its actual newly spawned child even when qualification fails, so
the enclosing fixture still owns its teardown. It requires actual live owned
type-4 state before completion. It does not wait for or invent native-node
recovery. Intent removal requires an independent fresh absent-file read. A failed
removal can retry after rechecking actual service state. An undispatched failed
intent can be cancelled after fresh unchanged-baseline observation. An uncertain
already-dispatched failure remains unresolved and cannot be changed into an
opposite-action success; the enclosing owned fixture must drain/recover it.
Foreign intent, unexpected process death, ignored stop, failed start or missing
observations fail closed and retain available recovery ownership.

The domain controller serializes its background process monitor with intentional
transitions. A slow valid mixer stop must not trigger whole-stack teardown.
Unexpected service/peer/domain death still fails the owning fixture. Healthy
whole-stack teardown retains the existing own-process cleanup; incomplete mixer
intent is evidence of an unfinished operation, never a passing feature cleanup.
The existing 20-second Chat operation deadline applies; allow up to ten seconds
for this control request, including guards, signal waits and private file I/O.

## Required full Chat composition

1. Before input, own/pin the private domain, actual peer, primary cache and service
   baseline. Keep the original primary/peer processes and native self identities.
2. Request mixer offline. Independently acquire actual primary **and** peer native
   mixer absence; a process-control receipt cannot populate `mixerConnected`.
3. Perform the normal primary Send. Observe actual UI/storage local fallback and
   original native `localOnly:true`; the separate peer must acquire fresh original
   receive history with no corresponding remote receipt.
4. Request mixer online. Independently observe matching usable fresh mixer UUIDs
   on both pinned sources. A new process PID alone is insufficient.
5. Preserve the three-second no-replay window with advancing original native
   samples, then type/send normally and verify actual ordered remote reception.
6. Cleanup restores an actually running owned mixer, verifies native recovery,
   restores peer/UI/settings and drains original receive caches/file descriptors.
   Independently require absent service intent and complete resource inventories
   before removing full-run ownership. This actuator alone proves none of those
   UI, network, source, peer or full cleanup joins.

## Host counterexamples

Fourteen focused cases cover surviving other owned workers, actual stop/fresh
start, idempotence, wrong type/start/owner, failed/uncertain/ignored persistence,
ignored signals, failed/ignored removal, foreign intent, transient original exec
reads, unexpected exit, failed start, false offline bookkeeping and closed input
vocabulary. Four domain-controller cases include the authenticated HTTP path,
bad token/version/fields, a deliberately slow mixer stop, unchanged actual
peer/domain/other-service PIDs, fresh mixer PID, independent GET and empty intent.
All pass. These are host test-logic checks; real node expiry/recovery, original
Chat delivery and all three clients remain unqualified.

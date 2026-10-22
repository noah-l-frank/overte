# Phone Create entity-sync foundation

The common `feature-create` suite requires `entity-sync` in both the catalog
and `FOUNDATIONS`. The Phone Appium adapter now implements the existing
`collaboration.edit` and `collaboration.snapshot` operations using the existing
version-1 domain actor and private client observations. This closes an adapter
registration/dispatch gap; no feature catalog or product behavior changed.

The default remains off. Set `OVERTE_ANDROID_E2E_COLLABORATION=1` only for a bound,
controlled physical Phone Appium target with an existing foreground session.
The existing fixture supplies `OVERTE_E2E_DOMAIN_ID`,
`OVERTE_E2E_DOMAIN_CONTROL_TOKEN`, `OVERTE_E2E_COLLABORATION_STATE_URL` and
`OVERTE_E2E_COLLABORATION_EDIT_URL`, plus `OVERTE_E2E_DOMAIN_URL`. Both control URLs must use the same private
IPv4 loopback origin and their exact version-1 paths. Redirects and environment
HTTP proxies are disabled. Credentials remain private.

The common Create foundations deliberately leave the application in a
serverless world. Before its first measurement this foundation therefore uses
the existing Appium `navigation.enter-domain` operation for the exact controlled
domain URL, through the existing session input scope. Three fresh advancing
native arrival samples must prove the actual controlled domain; an ignored
entry acknowledgement remains red. An existing journal cannot silently repair
a subsequently lost domain. No new navigation implementation was introduced.

The foundation does not repair an Appium session, evaluate a script, or mutate
entities through the Phone. Its measurement reads
the original `phone-collaboration-observation.json`, whose producer reads real
received entity properties, color and native `lastEditedBy`. That author must
match the independent assignment's actual `Agent.sessionUUID` in the existing
broker receipt. Exactly one entity, exact revision/value, fresh device epoch,
advancing sample sequence and the unchanged controlled domain are mandatory.
Actor state is read before and after the native sample. The final epoch read is
followed by ownership/deadline checks. Candidate bytes, source revision, process
PID/start ticks, Appium session/generation and target fingerprint are guarded.

The private version-1 owner journal pins those original identities, the control
configuration digest and the actual last actor/native sample. It is serialized
with the existing private source lock. The journal records one-send edit intent
before HTTP and retains it across failed or lost returns. An edit returns
`performed` only after independently measured actor and received-client effects.
Repeating an unresolved or confirmed edit cannot send it twice; a fresh public
snapshot consumes its confirmed intent. Uncertain edits remain recorded and
red. The existing domain fixture owns the shared entity and actor, including
their eventual teardown; this foundation creates no extra target resources.
Normal adapter cleanup, also when the opt-in is off, closes confirmed/consumed
history under that stable lock. It validates the full original sample at its
historical epoch, writes and reads back an immutable digest-named diagnostic
archive, and removes only the matching active journal. This host-only closure
can follow a later regular process change; no archived source qualifies a new
measurement or is used to bootstrap a later session. The stable lock inode
remains for coordination. A later SDK session can establish a fresh owner.

An issued/unconfirmed edit first requires a fresh actor/client acquisition
under the exact original candidate/process/session/control/peer. Ignored input,
lost original context, changed active files or archive collisions preserve the
active journal and fail cleanup; base SDK cleanup is still attempted. A lost
archive or unlink return can be retried without overwriting the original or
resending input. All files remain private; no native identity enters portable
observations.

Validation on the isolated source branch:

* 18 Phone foundation tests passed in 31.852 seconds. They run the actual
  `feature_capability_gate.py --area create` and unchanged `entity_sync.py`
  from a serverless initial world through real Phone Appium dispatch, the original JavaScript assignment and
  probe-property function, and the real collaboration broker over controlled
  loopback HTTP. Entities, Android private files, SDK and process are explicit
  synthetic seams. The tests prove that default-off produces mandatory gate
  failure, and reject ignored broker/actor/replication inputs, foreign or stale
  observations, missing sequence progress, replaced controls/credentials,
  changed candidate/PID/session/target, ignored domain-entry acknowledgements
  without SDK session repair, and a lost edit return without replay.
  Lifetime counterexamples additionally cover disabled-opt-in cleanup, an
  actual new SDK session after closure, repeated cleanup, lost archive/unlink
  returns, foreign active/archive replacement and unresolved or replaced
  original process contexts without forgetting one-send intent.
* Existing Phone feature cleanup regression selection: 54 tests passed in
  13.227 seconds, retaining all other owners and base teardown behavior.
* Existing Create registration: five tests passed (0.115 seconds).
* Existing collaboration actor/broker/observation: eight tests passed (0.098
  seconds), including execution of the actual original JavaScript readers.
* Existing domain actor reseeding: one test passed (0.032 seconds).

No native source changed, so no new compiler claim is made. No complete Android
build, Appium server, device, installation, network service outside loopback or
Jenkins was used. This is host-verified source composition, not device acceptance.

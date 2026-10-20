# Durable normal Script inputs, version 1

`_script_actions(selector, run, fixture_url)` returns `PhoneScriptActions`.
`prepare()` reserves the original cleanup scope and observes its actual native
location/absence without staging files or opening UI. `act(arguments)` accepts
the existing exact v16 `feature.scripts.act` input, including run, fixture URL,
ticket, verb and controlled inputs. It returns delivery acknowledgment only;
execution, effects, visible error, HTTP and actor facts remain separate evidence.

All operations hold the existing source lock and admit SDK input through
`existing_input_session`. Preparation requires no existing file/manager/restart
owner when creating a new run. It persists its own preparing record first, then
reserves the original file owner and separately observes native absence. Recovery
of a lost preparing write can reuse only that same run/context and actual absent
scope; it cannot adopt a foreign root or stage/recreate files. Preparation and
each input are bounded to 30 seconds, including private writes, with all existing
getter/UI/SDK/runner bounds retained.

Before every new input, the coordinator captures a fresh original native
execution/code/module/load/effect/all-known-manager barrier. Native birth and
actual SDK/process/candidate binding must match the run. It persists `issued`
intent, exact validated inputs, original binding and the whole original barrier
before sending the ordinary input. Tickets cannot be reused for another action.
The scope never sends a desired result or changes a state observation.

The concrete routes compose existing helpers:

| Verb | Ordinary input / separate ownership |
| --- | --- |
| `open` | On first use, one reserved fixture stage followed by independent original-byte verification; then ordinary tablet/Running Scripts open. Later opens never restage. |
| `picker-open`, `picker-cancel` | Existing actual Qt picker open/cancel, token/source/ownership validation. |
| `picker-accept` | Existing main/companion selection, review and Use Files input for the controlled single or nested bundle. |
| `stop-owned` | Existing observed owned row and its ordinary Stop control. |
| `restart-app` | Existing one-send application stop/launch, original lifecycle/kernel/process/Script/file handoff; no Script load or panel reopen. |
| `load-url` | Explicit stopped-file scope transfer preserving the actual open UI, then ordinary From URL with the current ticket's controlled missing URL. |
| `close` | Existing ordinary close; missing-load ownership first requires its original completed failure callback and independent service absence. |

A confirmed ordinary call records its original receipt and `acknowledged` phase.
A repeated exact acknowledged call rechecks actual admission/native birth and
returns delivery acknowledgment without more clicks, stop/launch or staging.
An ordinary issued call with uncertain delivery cannot be replayed into success.
Only the existing explicitly persisted restart protocol can resume its same
issued input through original OS/native evidence. Restart updates current
binding/native birth/file-owner snapshot only after the verified new process,
unchanged original files and kernel exit; the old input barrier remains intact.
A lost final journal return can resume only the committed acknowledgment.

The private `phone-script-actions.json` envelope has `scriptActionVersion:1`,
`sourceKind:"phone-script-actions"`, `runId`, `payload`. The existing bounded
canonical compressed metadata codec stores binding/native birth, fixture URL,
actual directory, original file-owner snapshot, phase, stage intent, distinct
tickets, current exact input/binding/native barrier/receipt and original restart
record. No expected state is stored. Original owner shape, context, hashes,
typed versions and historical restart counters are revalidated on read. Storage
retains existing private permissions, atomic CAS and the 64 KiB file cap.

Failure retains issued input and original cleanup responsibility. Ignored stage
ACKs fail actual-byte verification before manager input. Missing native failure
callbacks cannot close/discard unresolved load ownership. General cleanup still
runs base teardown and refuses success while the action journal remains; there
is no unconditional reset/discard method.

Eighteen device-free cases exercise the first ten normal inputs, actual missing
URL/close routes, ignored stage, missing failure callback, duplicate/foreign
inputs, lost normal and private returns, explicit restart/new binding, lost stop
ACK recovery, ignored launch, typed/foreign scope, deadlines and incomplete
cleanup. They use the actual Phone coordinator/helpers with synthetic SDK,
native/OS and controlled file boundaries. The fixture acknowledgment shape was
corrected to keep observation fields out of input replies; the production parser
remains strict. SDK acknowledgments do not establish product function. Native
code is uncompiled and devices remain untested.

The [full Script feature owner](SCRIPT_FEATURE.md) now composes this input
layer with original callback/readiness proof, owned HTTP404 receipts, explicit
per-role restart histories, independent publication and verified cleanup. This
layer's acknowledgment remains input delivery only. Physical acceptance is
unchanged; native instrumentation remains uncompiled.

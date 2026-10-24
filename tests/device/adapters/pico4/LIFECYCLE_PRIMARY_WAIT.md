# Private Lifecycle primary/session wait connection

`PicoLifecycleObservation.observe_operation` accepts only the existing
`feature.lifecycle-input.observe` request. It validates the portable contract,
original run and exact afterSequence, then uses the existing fresh reader.
It grants no public capability, action or cleanup operation.

The new test loads the unchanged `OverteSession` implementation and routes its
normal `feature_operation`/request/result validation to this private handler.
It invokes the unchanged `Journey.wait` for a primary-only pre-input baseline
and the actual Back negative window after the existing normal
Create/type/blocked-World/release/X prefix. Expected states come from the
unchanged common16-action recipe and stay exclusively in the consumer.
No expected state enters a native query or the adapter. Peer, artifact,
activation and report callbacks explicitly fail if called. This is a private
primary diagnostic, not the common baseline's peer evidence or `execute()`.

Every observe still acquires a fresh same-World UI/gesture/drive frame and full
Pending/Native originals. No saved frame is returned as a new sample. The
previous baseline fixture gained only injection points for this real consumer;
its existing owners, actions and native/Qt/OS/physics model seams remain.

## Actual costs

Evidence directory:
`/home/user/tmp/overte-pico-lifecycle-continuation-20261024-sCdPTg8o`.

The first run was red1/14.593s only at the new measurement assertion. Its
prediction of13 Back samples was wrong: the unchanged consumer legitimately
needed14. Original `lifecycle-editor-sb6f4p3l` and full-source SHA
`991589c49528949b55d8a2da782b56ba090f3e49cef115fa45f6eaf9e1fc40f9`
remain unchanged. Offline original reconstruction is saved as
`lifecycle-primary-wait-offline-originals.json`: Back source epochs
26502…29752ms, Host6.502…9.751999999999999,14 original queries. At the nominal
13th sample the original floating-point difference remained below3s; nothing
was retimed, rounded into success or removed.

The test-only correction records all stages/samples before assertions and
requires exact agreement between actual consumed samples, frame deltas and
dense global sequence, retaining the original ≥3s/<20s bounds. Runtime and
cadence were unchanged. One fresh same case passed **1/14.130s**, log
`lifecycle-primary-wait-corrected.log`, original `lifecycle-editor-cnt5gnrg`.
Full13475-file source manifests match before/after, SHA
`9322b0be33aa1d1bb6ab49a4814a8b1aa50e4aae128773451414ba566a3dcfee`.

| Actual stage | Same World frames | Delta |
| --- | ---: | ---: |
| Before primary baseline | 2 | — |
| After3 advancing/.5s primary samples | 5 | 3 |
| After existing first-four-action owner prefix | 22 | 17 |
| After unchanged Back ≥3s negative wait | 36 | 14 |
| After existing remaining Pending prefix | 102 | 66 |

The consumer admitted exactly17 fresh results, requests with afterSequence0…16
and17 completed original records. **102/128 frames** leaves26; no second
container resets that counter. The test retains its diagnostic JSON before any
assertion. It does not run Restore/Restart or a complete shared journey.
The earlier separate private Restore result cannot be relabeled as this flow.

## Review and remaining work

Depends on `35b2d4a89595b3a9ee133607ddc58fba84f8c8e6`. No wire/version/limit
changes. The existing `lifecycle-primary-baseline` selector gains exactly this
one case (3→4), keeping120s; one control-plane module pattern is added. No new
selector, catalog-count change or duplicate positive is introduced.

Public capability, independent Actor, images and full cleanup/return/archive/
Host finalization remain open. The next step is an actual per-stage query
budget for all ordinary advancing/negative waits plus existing Restore. A
future shared acquisition must be newly created within one owning call and
bind the exact World frame/cursors and both consumers' original intents. This
test shares no old acquisition and does not establish such a receipt yet.

Final lightweight checks: discovery finds exactly one new shared case and four
cases in the existing Pico baseline wrapper. Registry is coherent;
Coverage10/0.039s maps14/14 risks. Repository `documentation-contracts`,
`project-coverage`, `documentation` and `source-layout` all passed in2.63s;
`git diff --check` passed. No functional case was repeated for registration.

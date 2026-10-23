# Original Tablet echo chain

`tablet_web_echoes.chain` joins one actual document's original native sources,
ready DOM packet, complete UIKit input ledger and native Script-emission
ledger. It neither issues input nor queries or writes any source.

Current State2 composition also retains the actual presentation-target join.
UIKit input and presentation observations mint independent weak object IDs.
The current decoder uses the original State2 `presentation.target` and verifies
its exact generation/source and presentation snapshot; it never equates those
two namespaces. The state-less helper remains readable for the literal legacy
same-ID fixture contract, and current `tablet_web_history` always supplies State2
when the original frame has that source version. No stored DTO is upgraded.

The result separates four observations:

- `attempts`: trusted DOM bridge clicks with actual touch down/up originals,
  a matching original WK target/contact and normally returned UIKit dispatches.
- `delivered`: actual accepted main-frame WebChannel envelopes and native
  Script deliveries associated with those attempts.
- `accepted`: actual Script replies attributed to the admitted app manager,
  submitted root code, whole indexed V8 source/line/column stack and native
  API call, followed by its actual native slot and page-reply observations.
- `echoes`: those same replies actually received and displayed by the passive
  DOM observer in that same document.

An outgoing API call or native delivery acknowledgment creates no DOM echo.
Native delivery without an actual app reply creates no consumed-VM message.
A foreign document can have a genuine trusted attempt while retaining zero
deliveries, consumed messages and echoes.

UIKit contact and event object births remain separate from DOM gestures.
Contacts are associated in order with all actual touch gestures in the
document, with a maximum 1.5-second asynchronous delivery lag. WebKit may
deliver a DOM pointer event after `UIApplication.sendEvent` returns; a
synchronous return interval is deliberately not imposed. Canceled gestures
and exceptional or still-pending UIKit dispatches cannot qualify bridge
clicks. Actual UIKit weak death and final process retirement are separate
owners and are not asserted here.

The native trace's `Signal` entry occurs before its actual emitter `SinkScope`
member is constructed. Its trace return occurs before that member's normal
return/finally. The join checks that exact bracket and rejects ambiguous
same-shaped sinks; it does not require independently captured clocks to be
equal. Source identity, actual document nonce/frame/main-frame admission,
original message bytes, exact call ID, source stack and page receive remain
independent requirements.

Callers retain each historical document's own original active ledger and
validate source/history continuity separately. The completed native document,
real observer installation/hash, finish and verification are required here;
HTTP server response/origin and decoded inline-body provenance are separately
validated by `tablet_web_documents`.

The host fixture executes the generated ordinary Tablet app, unchanged
reference page and actual passive DOM observer in Node. UIKit, Qt and native
source DTO boundaries remain explicit host models. Tests cover a full genuine
host-JS reply flow, asynchronous DOM timing, actual V8 call locations, foreign
and synthetic attempts, missing receipts, native-source disagreement, wrong
caller/source/nonce/frame, ambiguity and incomplete document/dispatch
lifetimes. No native code has been compiled or run. Full Tablet observation,
ordinary actions and paired final retirement remain incomplete.

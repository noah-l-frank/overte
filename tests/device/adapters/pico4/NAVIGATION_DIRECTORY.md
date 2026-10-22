# Original consumed directory and normal Places search on Pico

This is an internal component of the unfinished Worlds/navigation adapter.
Native code is uncompiled, all Qt/SDK/VR boundaries remain host simulations, and
there is no device qualification or complete Navigation capability. Three of
fourteen areas remain source/host complete.

## Original provenance chain

The original Places fetch callback first rejects an obsolete requestGeneration,
shutdown or closed app. Only a current successful callback reads responseText,
parses the original directory, applies its real protocol filter and eventually
sends PLACE_DATA to the tablet. Rebuilds caused by ordinary search change the
filtered ListModel, while the underlying root.records changes on actual new
PLACE_DATA. A completed HTTP write, callback ACK or preloaded row cannot stand
in for that path.

Under both dedicated Pico E2E flags, XMLHttpRequestClass's original responseText
getter passively captures its first actual DONE/current-callback read on the
request/reply owning script thread. The unchanged original returned value is
preserved in every configuration. Admission requires the original Places manager
load URL, actual submitted UTF-16 source identity and load/manager instance,
actual final directory URL/query, actual HTTP 200/NoError, one unpredictable
fixture-response header, bounded original response bytes and the actual owned
row. It exports body byte count/digest and hashed owned row/protocol fields, not
raw bodies, unowned server lists, code, paths or credentials. A repeated getter
cannot give an old response a new identity or read time.

The original script-thread TabletProxy.sendToQml call additionally posts a
passive observation before the unchanged GUI queue hop. Its actual original
PLACE_DATA array is matched to that thread's original read and privately hashed.
The GUI re-entry does not duplicate it. The existing original Qt invocation and
product message are unchanged; no diagnostic member is inserted into a message.

The existing NavigationUi supplies the actual current Places root identity and
frame. The collector connects that original root's recordsChanged notification
to a passive slot on the already existing Test interface; no new moc target or
QtQuick dependency is introduced in script-engine. The slot only accepts its
actual signal sender and reads the already assigned original records. Actual
array digest and target-root identity match the pending original outgoing call.
It records the original message's actual delivery time, root revision and last
message ID. An unmatched later data notification clears that association.
A local search model rebuild cannot manufacture this records notification.
The native frameRevision also records which actual data revision existed when
NavigationUi read its original model. Joining requires frameRevision to equal
the current records revision: an older UI frame cannot borrow a newly delivered
response, even when both events share the same millisecond timestamp.

A GUI-owned application-property provider bridges the existing modules. Script
observations carry weak actual thread identity through the normal queued Qt
transport; the consumer never blocks or reads a foreign engine/reply heap.
Only bounded native facts and weak roots are retained. Histories contain at
most 128 original reads, messages and roots and 4096 unique query nonces. Clock
regression or exhaustion is unavailable. Original root death cannot resurrect.
This is data-consumption provenance, not an inventory or release verdict for all
Script/XHR/timer/callback resources.

## Closed reader and normal input owner

`native-navigation-directory` v1 is read by the closed nonce/run action
`feature-navigation-directory` through the existing lifecycle/private-file/PID/
candidate/source guards. The original probe writes only the fixed private
`feature-navigation-directory.json`. Missing sources stay unavailable. One
request sends once and reads at most 51 times within five seconds. Readers pin
source birth/cursors/UI clocks, immutable read prefixes, immutable message birth
and sticky delivery, weak roots and monotone original records revisions.

The independent provider receipt must match the native unpredictable response
ID, exact body bytes/digest, origin and original refresh ticket/time barrier.
The caller supplies the original qualified source revision, original Places
script URL hash, submitted UTF-16 code hash and code-unit count. Native values
must match that separately frozen profile; they are not derived from desired
results. Protocol and observed owned ID/name/address must match the original
provider inputs and the real controlled B viewpoint. Current root/source/frame,
actual records delivery and the independently read current ListModel must agree.

`navigation-directory-operations` v1 uses the existing private Pico factory and
TokenPlacesUI/PicoNavigation input. The parent owns and opens a loaded normal
Places page, selected origin and source/input lock. The initial page must be
idle, have an empty actual query, include Everyone maturity and have no queued
commands or active dispatch timer. The owner normally presses Refresh, requiring
new original read/message identities absent from that baseline. It then normally
focuses/types hidden-<run>, verifies no owned model row for three seconds, and
normally types e2e-<run> to recover the actual owned row. Search retains the same
original refreshed data provenance while using its current parent ticket.

Each exact normal input is journaled before one send. Applied lost refresh,
focus and typing replies resolve through actual input count/effects after owner
recreation, without resending or replacement tickets. A consumed input counter
alone cannot prove refresh, typing or results. Each operation has a twenty-second
ceiling and at most 81 effect polls per stage. Quiet windows require unchanged
original data provenance, actual query/model, native/UI time progress, no extra
input and gaps at most 1500 ms. The original UI generation, Places tab and
complete maturity selection stay unchanged; an unowned dialog or unsupported
lifecycle transition cannot complete the operation. No snapshot is retimed.

The private journal preserves full original baseline/current/quiet packets,
provider history, exact pending input, source profile and at most 256 unique read
IDs. It reuses the existing shared bounded zlib/base64 original-history envelope
(16 MiB raw / 48 KiB encoded) within the unchanged 64 KiB private CAS file limit.
Compression overflow is unavailable; no original is dropped to fit a journal.
Original prefixes and final quiet/current packet continuity are revalidated on
recreation. Missing, changed, stale or replayed evidence keeps ownership open.
The parent still owns page closure and whole-area resource/metadata retirement.

## Host verification and remaining work

The normal refresh -> hidden quiet -> owned recovery flow, private Pico factory,
original probe and actual owned short-lived loopback HTTP response/header/write
receipt are exercised on the host. Native/Qt/provenance boundaries are explicit
simulations. Counterexamples cover a preloaded current row and old read, no new
HTTP consumption, outgoing-only or missing actual records delivery, ignored
refresh/typing, lost replies, source/code/protocol/receipt/root mismatch, history
and query tampering, frozen clocks and extra input/data changes during quiet.
Original Places fetch JavaScript executes under Node and verifies that obsolete,
closed and duplicate callbacks cannot read or republish an old response.
No test compiles or executes the C++ additions or qualifies native queue ordering.

Next compose actual row selection and B/A native arrival/stereo observations,
normal maturity preservation, remaining owned Go To closure, actual process
restart/bookmark transfer, independent publication and complete resource quiet
retirement. Keep the complete feature capability absent until that whole path
and final ownership retirement are integrated and host verified.

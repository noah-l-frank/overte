# Offline Chat Send and restored-mixer no-replay window

Feature 10 remains partial. The internal
`IOSChatDraftRuntime._chat_offline_send_operation` factory reuses the existing
paired receive admission and normal draft owner. It adds no public operation or
complete capability. Connected `original_sent` validation stays unchanged.

Normal Send uses the existing durable input journal. Independently acquired
native originals must show mixer absence, exactly one local-only self echo
matching the actual submitted draft, and unchanged peer histories. The first
actual append is authoritative; a wrong flag or foreign append cannot be
skipped. Emptying the editor or acknowledging input proves no message effect.
The derived local echo explicitly establishes neither remote delivery nor
Domain continuity during the outage.

After mixer restoration, a separate private journal owns only the passive
`await-no-replay` window. It saves the original phase and receive cursor before
acquisition. Recovery adopts an already saved cut through the existing receive
owner without another query or Send, preserving its file identity and clocks.
Three advancing original cuts must span at least three seconds on host epoch,
host monotonic and both native clocks. All retained intermediate cuts must
preserve source/process identity and exact primary/peer event histories.
Restoration itself sends nothing. A later retry requires explicit ordinary
retyping and a new Send ticket.

The historical result is recomputed from original files. Reopening it cannot
write, query, issue input or refresh timestamps. Successful window validation
does not retire its journal, session scope, page, source or SDK responsibility.

Four initial and two disjoint five-case host selections pass all **14 distinct
cases** before relocation into these public source paths. They execute the
repository's production `armored_chat.js` in real Node children and use real
private files, locks and journals. They cover lost Send and saved-cut returns,
missing callbacks, acknowledgements without effects, unexpected peer delivery,
deferred replay, false local-only flags and stale/foreign native cache identity.
All 14 children run Script end, remove subscriptions, exit and close streams;
all 42 genuine temporary directories and registered cleanup responsibilities
are retained and drained. The final five cases pass in 48.034 seconds.

The lower Qt/native clock/cache, message bus and SDK producers are explicit
host models. No MessagesClient, real mixer, Domain, iOS process or device runs.
Current public-path execution is a separate pending integration check. Native
compilation and devices remain unverified. Complete loaded peer composition,
actual peer movement/publication, full UI observations, admitted-history
restoration and native/page/callback/source/process/SDK end still have to join
the unchanged 25-step journey before complete Chat capability can open.

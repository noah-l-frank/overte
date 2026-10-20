# Original Chat UI and stored history source v1

`ChatViewObservation.h` and `adapters/native_chat_view.py` add a passive source,
not a complete `feature.chat` adapter. Native code is uncompiled; devices are
untested. Thirteen host cases exercise original JS/Python paths with synthetic
GUI/settings state only. No full capability is advertised.

## Request and acquisition

The exact private command is `{schemaVersion:1,commandId,action:
"feature-chat-view-observe",runId}`. Nonces are 32 lowercase hex characters,
prefixed `ios-` only on iOS; runs are 32 lowercase hex characters. Expected
values, text inputs, arbitrary settings keys and mutation operations are refused.
The original native response goes to `feature-chat-view-observation.json` in the
existing private results directory. Missing hooks and wrong nonces are unavailable.

The hook exists only in E2E builds with explicit `--testScript`, results location
and valid lifecycle source. Native reads run on the original GUI thread, bounded
to 4096 nodes/depth 128 and 1500 ms. Native wall-clock regression disables the
source. Envelope fields are exactly `chatViewVersion:1`, `commandId`, `runId`,
`instance`, `sequence`, `processId`, `capturedEpochMs`, `source`. Instance is an
actual source birth nonce; PID, increasing read sequence and time are native.

The host uses existing installed-code/process/private-profile guards before and
after acquisition, sends once and polls for at most 5 seconds/51 reads. Run,
instance and PID stay pinned; sequence advances and native time cannot regress.
Android retains target-clock freshness (-250..1500 ms). iOS retains native time
with a bounded actual AFC/PID transaction; host UTC never replaces native time.
Missing, duplicate-key, malformed, oversized, foreign, stale and late sources fail.
This component does not solve iOS installed-code association or shared command-slot
serialization. A full coordinator must serialize independent target transactions
and preserve the canonical iOS refusal until code association is implemented.

## Source fields

`source` has exactly `tabletShown`, `editorFocused`, `editorHasDraft`, `keyboard`,
`ui`, `storage`. Focus and draft-presence inspect original editors even when
hidden; retained hidden drafts/focus cannot become successful close cleanup.

Absent `ui` is exactly `{present:false}`, with no invented channel/history.
Present UI fields are `present:true`, `generation`, `channel`, `draft`,
`keyboardRequested`, `localMessages`, `domainMessages`, `visibleMessages`,
`localRowCount`, `domainRowCount`, `visibleRowCount`. Generation changes on actual
page/window/presence transition. The original QML context, root/tablet mode and
typed aliases must resolve. Local/Domain aliases are actual GUI-thread
QAbstractItemModels. The original QML-id `listview` independently supplies its
actual bound model; a wrong binding stays wrong. Hidden lists have no visible
rows. Original order/multiplicity survives. Counts cover all original rows
(0..1000); exported messages contain only the four controlled run texts. A
private/foreign editor refuses acquisition without exporting its text.

`keyboardRequested` is only QML intent. Actual `keyboard` is `{available:false}`
or `{available:true,backend:"native-touch-metrics",visible}` from native OS-derived
runtime metrics. Pico VR entity keyboard lacks this qualifying source and must
block projection. A missing measurement never becomes false.

`storage` has exactly `kind`, `count`, `unowned`, `events`, `configSha256`.
Original live recursive-locked Setting::Manager supplies atomic presence/values
for fixed `ArmoredChat-Messages`/`ArmoredChat-Config` keys. Kinds preserve `unset`,
`null`, `empty-string`, `array`, `string-list`. At most 1000 original entries are
read. Actual accepted run-message maps retain only `{channel,text,timestamp}`,
where timestamp is original positive Date.now() milliseconds no later than the
capture. Other entries increment `unowned` without exporting private content.
`count == unowned + len(events)`; stored strings are not accepted-message maps.
Config exports only SHA-256 of original QDataStream-encoded presence/value with
bounded scalar/map types and size, never raw private settings. This hash proves
equality of reads, not executable identity or file durability.

`measured_view` projects only UI fields, never peer delivery or persisted history.
Missing keyboard blocks it. Closed UI requires absent draft/focus/keyboard and
uses channel `none` because there is no active page. Settings is not a Local or
Domain view. Visible rows are never synthesized from aliases or stored events.

## Cleanup and complete adapter handoff

This endpoint is read-only and creates no Chat cache/message/settings mutation.
The full owner must remove original private command/response files after proving
no in-flight reader/writer with original inode/process guards. It must close the
actual page, retire receive caches, restore exact original private history/config
and require two fresh final inventories. Normal Erase must clear the actual Chat
script messageHistory too; settings writes alone cannot prove that. Unowned
history prevents destructive cleanup. Complete cleanup is still missing here.

Remaining joins include independently bound peer send/movement, actual mixer-node
recovery, VR keyboard, lifecycle/position effects, settings restoration and an
independent evidence publisher for all ten Chat state fields. Send ACK, editor
clearing and local receive echo are not delivery. Register a full triple only
after these joins and cleanup counterexamples exist. Coverage stays adapter
missing/device untested.

Counterexamples cover wrong visible bindings; distinct model/storage inventories;
order/multiplicity; hidden draft/focus/keyboard; requested-vs-actual keyboard;
missing/ignored/foreign nonces; PID/run/instance/sequence/time loss; privacy and
closed metadata; actual fixture admission and original JS dispatch.

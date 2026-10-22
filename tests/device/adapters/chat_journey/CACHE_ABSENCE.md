# Original passive Chat cache absence

`ChatCacheAbsence` v1 uses the exact existing `ChatSamples` query, immutable
chunk, reconstruction, source-lock, wall-clock and host-clock implementation.
It has a separate journal tag and separate fixed initial/final primary, actor
and witness paths. It is deliberately not a `ChatSamples` subtype that an active
input owner can accept. Existing active v4 journals and active cache resource
accounting are unchanged.

Each capture independently queries the actual primary and peer native cache
inspectors, real primary VR keyboard/QML/storage and native lifecycle. It never
calls cache begin, observe or retire. Both original native scopes must actually
be absent, with zero opened time, event sequence, dropped events and rows. A
never-created scope and an actually retired empty scope remain distinguishable
in the archived originals. Chat must actually be closed, its editor unfocused
and empty, its measured entity keyboard hidden and its accepted stored/UI
history empty. Original physical settings-file proof remains separately owned
by the original profile/settings barrier. Native original mixer identities and domain connection births
remain joined independently. Full candidate observations require native Chat
v2 domain evidence, including actual original connection birth.

Only those actual cache/panel/editor/keyboard absences yield an empty scoped
resource list. A live cache is refused rather than filtered out. Full feature
closure additionally requires original profile restoration, input files/FDs,
callback/timer ownership and old Qt/process retirement; this component neither
retires their journals nor supplies those missing proofs. Initial and final
absence transcripts cannot adopt/reset an earlier active history. Base teardown
retains all six fixed passive journals until their enclosing owner closes them.

Focused host tests exercise the same actual collector and explicit synthetic
native/view boundaries, including active-cache, page, focus, keyboard, storage,
source-mode and domain-reconnection countercases. The existing real Qt5 harness
also runs the original `MessagesClient::featureChatObservation` body,
`DomainHandler` setters and native `ChatObservation`: initial inspect stays
absent, an active original event is recorded, real retirement empties that
scope, and later original reception cannot repopulate the retired scope.
Network/NodeList transport remains an explicit seam. No application, native
Assignment Client, live network/domain, device or whole Chat flow was run.

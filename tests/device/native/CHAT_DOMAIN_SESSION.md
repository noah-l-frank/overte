# Original DomainHandler session source v1

Chat observation v2 adds the actual original DomainHandler session to the
existing native Chat result and owned actor transport. It introduces no new
controller, network service, command file or observation input. Normal builds
and launches without `--testScript` retain their original behavior. Full native
networking translation units/application/Android linking and devices remain
unqualified; the focused real Qt5 proof is described below.

`DomainHandler::featureChatSession(const QString& run)` is an internal native
getter, not a script input. The dedicated E2E member exists from the original
DomainHandler's construction and records actual UUID assignment, actual direct
UUID clearing in disconnect and actual connected-state transitions immediately
after the original field assignments and before their ordinary signals.
Original-thread checks, a short mutex and native clock regression fencing protect
its recorded state. It never reads a requested domain, URL/host, fixture ACK or
an adapter sample's first-seen time as the connection source.

The getter returns domainSessionVersion 1, instance, revision, connected,
domainSha256, connectionBirth and connectedEpochMs. Instance identifies this
actual original DomainHandler lifetime. Revision advances for each actual UUID
or connected-state change. ConnectionBirth is created only at an actual
false-to-true connected transition; connectedEpochMs is that original event's
native time. A same-domain disconnect/reconnect therefore changes birth and
revision. UUID A-to-B-to-A cannot hide behind a final matching UUID because
revision advances. DomainSha256 hashes this run plus the actual UUID bytes using
the existing Chat identity format; raw domain UUID/hostname never enters Chat
output.

Disconnected snapshots have connected false, empty connectionBirth and zero
connectedEpochMs. DomainSha256 remains the hash of the actual retained UUID when
one remains, or an empty string after original UUID clearing. Before any actual
connection there is no invented birth: revision is zero and connected is false.
A transient connected state with a null actual domain UUID is unavailable,
including a serverless scene without an actual network domain. Neither an
initial query nor a periodic sample creates a connection birth.

The original `MessagesClient::featureChatObservation` reads this original
snapshot before and after the existing locked NodeList session UUID and actual
MessagesMixer node/socket reads. It refuses a changed domain snapshot, changed
self UUID or replaced mixer node during acquisition. It adds actual mixerActive
to session, then records the actual original receive-cache result as chatVersion
3. Existing v1 packets remain readable for partial components but supply no
domain proof. Mixed legacy/domain-aware primary/peer joins fail. Both domain-aware clients must be
connected to the same actual domain hash, with distinct native source lifetimes,
and a present mixer must have an actual active socket. Across the whole source
transcript, original domain birth/revision/UUID/connection time stay pinned even
while the mixer alone disappears and returns. Local source state cannot be
replaced with a fixture process receipt or an outgoing message.

The Qt5 check compiles complete original DomainHandler setUUID, setIsConnected
and disconnect bodies, the complete original MessagesClient observation method,
both entire native headers and real QObject metadata. Network I/O, logging and
the NodeList transport are explicit seams. It exercises actual setter/event
tracking, same-domain reconnect, hidden UUID A-to-B-to-A, disconnected JSON,
different native handler lifetimes, actual inactive/absent node state and races
across the source acquisition; a separate no-testScript run verifies gating.
This does not compile the entire original networking class/translation unit or
run a network. Focused host reader/source tests cover closed v2 types, original
actor-file compatibility, mixed legacy peers, disconnected domains and changed
native birth/revision. The next mixer owner must join these sources to the
existing dedicated fixture-owned `-t 4` process control, preserve all other
actual fixture processes and independently prove absence/recovery/no replay.

Native Chat v3 additionally records `openedCommandId` and `retiredCommandId`
from the actual first accepted Observe/Retire mutations under the same original
receive-cache mutex. Passive Inspect, repeated Observe and repeated Retire
never replace either original ID. Retiring an unopened run has only a retirement
ID. A retired run cannot reopen; late receive signals cannot repopulate it.
The retained bounded ID fence is historical metadata, not an active receive
cache or a proof that the entire native QObject/process has been destroyed.
Older v2 packets remain readable for existing partial domain joins, but cannot
prove original mutation ownership to the new whole-journey cache owner.
The actual Qt5 source-body harness independently serializes initial, opened and
retired packets and feeds those exact C++ originals to the Python v3 validator.

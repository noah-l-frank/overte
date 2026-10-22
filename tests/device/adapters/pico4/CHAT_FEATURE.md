# Pico Chat continuation

Chat remains partial: no complete `feature.chat.act|observe|cleanup` triple is
advertised. The shared v16 journey still requires all 25 checkpoints and every
original observation, error/recovery and cleanup obligation in the
[source contract](../../feature_journeys/CHAT_SOURCE.md). Native sources below
are uncompiled and devices are untested.

The current original normal-input route is `PicoChatIO` over the existing
candidate/process/OpenXR-bound `PicoNavigation`. `TokenChatUI` opens CHAT,
focuses/types the controlled Unicode inventory, selects Local/Domain, sends
once through normal Send/Return and closes through normal BACK. It preserves
captured original draft/channel/focus tokens and caller-owned input intent.
Editor clearing and consumed input are not remote-delivery evidence.

The [passive Chat view source v2](../../native/CHAT_VIEW_OBSERVATION.md) now
reads the actual Pico entity keyboard instead of Phone OS inset metrics.
`Keyboard::featureChatObservation` exists only under the dedicated E2E and
Pico macros, requires `--testScript`, actual HMD mode and the original GUI
thread, and never creates/raises/changes a keyboard. The public private-file
hook still requires its original process/lifecycle/results owner.

The source preserves the keyboard QObject birth nonce, advancing original read
sequence, created/enabled/raised flags, active layer, HUD/entity dispatch mode,
original retained input target, current keyboard-focus entity and current HMD
tablet-screen UUID. It exports every actual key UUID/layer/pressed flag and
every owned original key/anchor/display/back-plate entity's type, local host,
parent UUID and visible property. No key label, typed display text, arbitrary
entity name or source URL is exported. Missing/foreign/deleted owners and
incomplete loading are unavailable. The anchor is intentionally invisible in
the product; actual visibility is independently recomputed from the remaining
entities, including inactive layers.

The Pico reader requires v2 and the VR backend, pins keyboard birth and
advancing source sequence, and refuses producer downgrade. The shared reader
retains explicit v1 compatibility for existing Phone/iOS sources. Measurement
rejects pressed keys, visible inactive-layer keys, a mismatching raised flag,
hidden active keys/display/back plate, disabled visible keyboards and a HUD or
foreign retained input target. A visible Chat keyboard must target the current
actual tablet-screen owner. A closed projection requires no visible keyboard,
draft or focus. These are current source properties, not rendered-pixel or
physical-keyboard qualification. They do not prove resource-request/callback
retirement; the complete owner must still acquire those original inventories.

Focused host counterexamples use synthetic GUI/settings/entities and the real
Python/JS control boundaries. They cover hidden/stale keys, original owner and
sequence replacement, touch-source substitution, missing inventory, foreign
parent/type/host, extra private fields, dispatch-target mismatch and version
downgrade. No device, OpenXR session or native product was executed.

The private `_chat_samples` factory now composes `chat_journey.samples.ChatSamples`
with its original admitted/active primary cache and installed Pico binding. The
caller must supply the separately qualified actual peer reader/binding and both
shared original source locks. The factory cannot launch, adopt or invent a peer.
Primary and actor roles keep separate private transcripts and issue their own
original primary/peer/view/lifecycle queries. Only `inspect` is used on native
caches; sampling cannot open/retire a cache, send a message or control a service.

Every read persists uncertainty before the first query. The whole acquisition
must finish within 1.5 actual host-monotonic seconds; original primary/peer
wall clocks stay separate. The oldest primary/UI/lifecycle originals remain
fresh and after the input fence. An interrupted role transcript cannot be
reconstructed as ready or replaced by a previous successful sample. Ready
reconstruction validates all originals and restores source/query/history floors
without live transport calls; the next result requires four new original reads.
Transcripts reuse the existing bounded private original-history codec, retaining
original query IDs, native birth/PID/open epochs, immutable arrival order and
multiplicity, configuration hashes and storage history. They admit no unowned
history and never serialize other users' message bodies. A stored accepted row
must match an actual primary native arrival subsequence, and original visible
models must agree independently with stored Local/Domain histories. Distant
Local cache entries do not become accepted/UI rows. Actual peer remote arrivals
exclude self echoes, foreign senders and `localOnly` events without deduplication.
Both native sources must witness mixer absence before a new matching mixer can
establish recovery; reappearance of the old cached mixer fails. The returned
resource projection covers only currently acquired panel/input/cache facts;
it is not the full original callback/file/resource lifetime inventory.

There is deliberately no source-transcript retirement method here. The future
whole-run owner must retain both role transcripts through independent final
restoration and actual resource retirement. Existing adapter process teardown
refuses green cleanup whenever either transcript remains, preserving the file
even after force-stop. A stopped process cannot retrospectively qualify
unresolved role ownership.

Twelve additional host cases exercise these original joins, separate role
queries, lost acquisition/journal recovery, old/foreign/half mixer state,
wrong UI/storage binding, missing original arrivals and retained teardown
ownership. The source boundaries are synthetic; this is neither a full normal
Chat input journey nor an actual product/network/keyboard qualification.

Next executable joins are normal independently bound peer Send and measured distant position/return;
owned mixer remove/restore with fresh native-node association and a full
three-second no-replay window; actual background/resume effects; original
private profile/config/history restoration; actual callback/file/cache/actor
quiet release and durable uncertain-input recovery. The existing actor
heartbeat and service ACK cannot supply these facts. Unresolved input or
resource ownership must retain its journal. Complete capability admission
remains closed until the whole flow and its cleanup counterexamples exist.

Shared integration points are `native-chat-view` v2 (explicit reads 1/2), the
shared passive Chat native hook/reader and E2E-only Pico keyboard code. No Phone
or iOS worktree/product input path is changed. Contract registry updates travel
with this packet and require reconciliation with concurrent local additions.
The second packet also registers `chat-journey-samples` v1. Existing shared
Script source locks/history codec and native lifecycle restoration are reused;
the common journey remains v16 and no complete Chat operation is registered.

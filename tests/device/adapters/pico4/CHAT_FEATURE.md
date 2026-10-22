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

Next executable joins are independent fresh UI/storage/native/peer sampling;
normal independently bound peer Send and measured distant position/return;
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

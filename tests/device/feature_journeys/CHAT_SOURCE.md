# Chat source and adapter boundary, common journey v7

The reviewed Phone (`718d069add`), Pico (`c5bf8ac17b`) and iOS (`864f8b79a4`)
product bases contain identical relevant sources:

| Original file | SHA-256 of UTF-8 bytes |
| --- | --- |
| scripts/communityScripts/armored-chat/armored_chat.js | 72ceb585d6071fb747102b0c97b6799dffab5f55df9619c83b41fcd510b02e5e |
| scripts/communityScripts/armored-chat/armored_chat.qml | f502702f77cc08142ba15e695e7c57292c299da4fb9eb269fbbf409b868a4311 |
| libraries/networking/src/MessagesClient.cpp | 8df18793957a686378a9f4f874f40534841a97660900f0141370b61b36648038 |

These source hashes document review, not installed-code association or proof of
which runtime engine/QML component is active. The shared Main copy can have an
earlier mobile presenter; select the actual submitted source and original QML
context before choosing an input recipe. Do not infer a profile from CHAT text.

## Actual inputs and observations

Normal CHAT opens armored_chat.qml. The QML pageVal starts at local. Tab pointer
inputs select local/domain; messageInput aliases the actual TextArea, chatSend
the normal Send button and chatClose the normal BACK button. Close navigates Home,
ends typing/focus/keyboard and destroys the page; an unsent draft is discarded.
Reopening rebuilds original saved history and selects Local again. Ordinary Send
or Return invokes the existing script and clears the editor immediately. Its
focus/keyboard aftermath can vary by input recipe and is read, not invented.

The script receives Messages.messageReceived, validates actual JSON, channel and
Local positions, rejects Local distance greater than 20 metres, stores actual
accepted messages in ArmoredChat-Messages and emits show_message. The QML keeps
separate models and selects only the active channel for display. A Domain row
arriving while Local is visible is retained. This is channel selection, not peer
blocking. The distant peer stimulus must move the actual owned peer at least 30
metres from the measured client position, send normally on Local, verify actual
remote position/send and return it; a forged position field is not the stimulus.

MessagesClient::sendMessage with no MessagesMixer calls messageReceived with
localOnly=true. The real Chat receiver accepts this controlled local echo;
the legacy compatibility packet carries forApp and is ignored. No-mixer Send
therefore clears the editor and adds exactly one local Domain row. It does not
prove remote delivery. A generic dropped socket while a mixer node remains is a
different boundary and cannot be substituted for network-remove-mixer.

The fixture controller must stop only its owned MessagesMixer, independently
observe absence of the actual native node and absence of remote delivery, then
restart that same owned service and observe a usable fresh mixer connection.
Keep the domain/entity/avatar services, tested client process and actual peer
identity owned and stable. Reconnection alone sends nothing. After three seconds
of fresh no-replay observations, retype the same controlled text and use normal
Send. Local Domain history then has two copies of retry; actual remote reception
has one. These lists must not be de-duplicated or synthesized.

peerMessages records only this run's outgoing client messages actually received
by the independently bound peer, preserving order and multiplicity. It excludes
peer-originated messages and legacy forApp packets. Verify actual sender/domain/
peer identities, source generation, immutable reception sequence/time, closed
Unicode payload inventory and localOnly=false. Both the primary read and the
independent publisher obtain their own current original ledger observations.
Outgoing packet creation, script send calls, local model rows or fixture input
ACKs cannot populate the remote ledger. No desired facts are sent to observers.

## Timing, ownership and failure

Existing 20-second checkpoint deadlines and 1.5-second fresh-source limits apply.
Chat close/distant-peer/removal/restoration/no-replay checkpoints require three
seconds and advancing independent samples. await-no-replay sends no product or
peer input and starts no timer on behalf of the product. Typed state requires
actual channel/visible rows to agree and a raised keyboard to have editor focus.
A failed actor or absent node/source makes observation unavailable, never an
empty received list. Missing mandatory abilities keep the full Chat gate closed.

Before mutation persist process/code/session/domain/peer ownership, actual
original private Chat settings/history, original peer position and service state.
Never clear pre-existing messages or adopt a matching display name. Use a private
controlled profile and fresh owned run; admit only its unpredictable text values.
Cleanup closes the owned view, releases keyboard/world-input routes, restores
peer position, confirms the owned mixer is running, restores original settings/
history and drains all owned actor work before journal removal. Keep unresolved
intent if service recovery, UI close, original storage restoration or actual
peer drain fails. Host source/reducer simulations prove only adapter/test logic.

The [native reception/cache source v1](../native/CHAT_OBSERVATION.md) and its
private factories now exist on all three source branches, with actual native
mixer presence/session reads. Full normal controls, independently read original
UI/storage and domain-node association, a separately bound actual remote peer
ledger, authenticated actor publication, service orchestration and whole-run
cleanup are still required on all three adapters. The existing domain
peer's movement/heartbeat supplies none of those Chat delivery facts. Native
instrumentation is uncompiled and all physical tests remain unperformed.

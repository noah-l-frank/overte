# Chat source and adapter boundary, common journey v10

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

## Version 10 active-page and independent UI correction

The closed page has no active channel: report `channel:none`, empty draft/visible
rows and no actual editor focus/keyboard. Never return the QML default local as
a measured property after the component was destroyed. Ordinary reopening must
measure the new original page's actual Local channel and stored history.

All ten Chat state fields are now independently witnessed, including draft,
focus and **actual** OS/VR keyboard visibility. Open/type checkpoints require
peer evidence too; declaring extra witness keys without checking them during
typing would allow a fake empty draft/focus witness to pass. QML keyboardRaised
is only a request and cannot populate actual keyboard. Tab pointer focus/keyboard
aftermath is read and may be either valid source outcome; a raised keyboard
still requires actual editor focus. The native QML MouseAreas do not explicitly
blur the TextArea, so the contract must not invent that side effect.

The 25-step flow now includes real background/resume after reopening/selecting
the retained Domain history. Require actual native lifecycle advancement, the
retained original channel/history and released editor focus/keyboard on resume.
Ignored lifecycle input, reset channel, lost history or a ghost keyboard fails.
Source-correct closed-page cleanup and all original native/source/resource
requirements remain mandatory. Full adapter implementations are still missing.


## Normal cleanup controls (2026-10-22)

The E2E-only Chat control inventory now identifies the original Settings tab
and Erase button from their original QML context and control structure. The
adapter sends ordinary Qt pointer events, records durable input intent first,
and requires fresh original channel/model changes. An input acknowledgement
never proves persisted history removal; the complete owner must separately
read storage and verify exact original history/configuration restoration.

`test_token_chat_ui.py` covers both model erasure and consumed-but-ignored Erase
while preserving cleanup intent. `phone-chat-native-test.py` compiles the
original control helpers against installed Qt6 and loads the actual original
Chat QML. Its ordinary channel, Unicode editor, Send, Settings, Erase and Close
events pass; a foreign overlay blocks input. Send leaves both receive models
empty in this harness, deliberately proving that an input signal does not
create delivery evidence. This is a desktop host seam, not an Android product
build, MessagesMixer roundtrip or device/rendering acceptance. The public Chat
owner and common journey remain incomplete at this source packet.


## Dedicated native peer input source (2026-10-22)

The existing owned Assignment Client file channel now accepts a second closed
command kind, `feature-chat-peer`. It permits only Inspect, Lease, four fixed
run-scoped peer sends, and Restore. Requests cannot supply message text,
identity, coordinates or delivery results. Its native output is a distinct
`chatPeerVersion: 1` pose/input source; the original `chatVersion: 1` receive
ledger remains separate. The host rejects an ordinary receive reply where a
peer source is required, and retains ownership on this failure.

Only the explicitly opted-in fixture actor configures this source. Agent binds
its actual downloaded script digest and actual ScriptableAvatar position
read/write callbacks. The existing deterministic fixture update pauses its own
trajectory while the native lease is present, including its phase counter.
After actual pose stability the native helper captures the original position.
Peer messages go through ordinary `MessagesClient.sendMessage`; the payload
contains the position read back from the actual avatar after any controlled
move. Distant Local moves the owned peer 128 metres on X; the complete adapter
must still independently measure its distance from the actual primary. Each
fixed send operation is consumed at most once, before any mutation. Lost
results cannot authorize replay. A foreign pose blocks further sends and
restoration. Restore reads the actual handback before releasing the lease and
retains that immutable event as the original trajectory resumes.

`phone-chat-peer-native-test.py` builds and executes the actual Qt6 peer,
receive-cache and file-channel helpers against explicit synthetic pose/network
producers. It verifies stable-pose admission, actual payload pose, no receipt
from Send alone, separate receipt production, duplicate-send refusal, original
handback, resumed motion, replaced-pose refusal and actual native IPC output.
This does not compile Agent.cpp or MessagesClient.cpp, run an Assignment Client,
prove mixer delivery, or exercise an Android device. Eleven host peer-source
counterexamples, sixteen private file-channel tests and ten independent receiver
tests pass. The public owner/common journey is still pending in this packet.

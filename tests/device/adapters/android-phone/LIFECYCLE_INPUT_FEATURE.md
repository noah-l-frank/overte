# Phone Lifecycle/Input implementation

This work is in progress. No complete `feature.lifecycle-input.*` triple is
advertised by this component. World gesture attempts, effective drive/position,
independent actor/image joins, mandatory foundation composition and the v18
fixture-closed finalizer remain separate required work.

## Original editor source v1

`Test.phoneLifecycleEditor` requires the default-off Phone E2E build,
`--testScript`, existing native lifecycle/private-results scope and real
OffscreenUi/Tablet providers. `phone-lifecycle-editor-{observe,input}` accepts
closed requests and writes original responses through the existing owner-only
atomic private file channel. Read-only command admission allows observe only.

`PhoneLifecycleEditor` walks the real rendered tree, binding the exact canonical
PathUtils-configured original Create, armored Chat and Running Scripts QML URLs
and their original `newText`, `textArea`, `filter` identities. A same-named field
from another QML source is unavailable. Weak page/context/field/window identities
receive non-reused opaque tokens only after real acquisition. History retains
creation/retirement times and current alive/attached/active facts. Temporary
background visibility loss preserves the same actual Chat identity; a destroyed
and recreated Scripts editor receives a new identity. Request order supplies
no generation. The public reducer must join these originals to its owned
workflow before exposing shared generation facts.

Current text/focus/frame and actual platform keyboard visibility are original
reads. Keyboard visibility comes from Tablet's validated Android runtime metrics,
not QML keyboard requests. Only empty or the corresponding closed per-run Create,
Chat or Scripts draft may leave the source. Unexpected private drafts, missing
roots, ambiguous current fields or invalid identities return unavailable.

Focus uses the ordinary Qt pointer route. Type uses the existing native IME
helper on the actually focused field. Neither directly invokes a QML handler,
sets text/focus properties nor submits a draft. Native input consumes its nonce
before a source/token lease can fail; an uncertain/rejected admitted command
cannot replay. The Python transport persists supplied intent before one send,
then requires fresh independently correlated originals. `performed` is an input
receipt; no text, keyboard, focus or complete feature result is inferred from it.
The existing five-second operation, 1.5-second freshness and bounded history
contracts remain. Missing/dropped/retimed source histories remain red.

Local component tests compile and run the actual new Test method, original
Create/Chat/Scripts QML pages, native pointer/IME helper, PendingFieldCommitOwner
and actual PreparedFieldCommit implementation with Qt6. A real held IME event
is rejected by its original context guard after destroying the old Scripts
page and creating a new unfocused empty page. Backend services, native test
lifecycle, PathUtils deployment roots and OS-IME metrics are explicit host seams.
Those tests do not attest Android IME, application rendering, a full Android
translation-unit build or device behavior. Separate reader/probe counterexamples
cover input ACKs without effects, closed grammar, missing original sources,
read-only mutation refusal and immutable weak identity history. Central admission
pins and global profile counts remain integration-owned.

# Internal Chat unsent-draft owner

`IOSChatDraftRuntime.draft_owner` uses the existing installed-candidate runtime,
existing SDK session and exact Script source lock. It is an internal partial
owner. Configuration admission, catalog dispatch and complete Chat capability
remain unavailable. Native instrumentation is uncompiled and devices untested.

The same owner now writes version two and reads literal versions one and two.
Its [normal local Send/history continuation](CHAT_MESSAGE_OWNER.md) adds channel
selection and independently observed local acceptance. Literal version one
retains the draft-only grammar described below. No old record is rewritten.
The runtime also retains an external-artifact scope before input; ordinary
session operations remain blocked while any unfinished `ios-chat-` ownership
exists. Closing the page does not retire persisted messages or the scope.

The normal tablet/Home and CHAT entry must already be available. Admission reads
an absent Chat page, no focused/hidden draft or actual keyboard, and an empty
persisted history with no unowned entries. A private existing page/draft/history
is never cleared or adopted. The original configuration digest must remain
unchanged. Literal version one also keeps the exact storage kind/body unchanged
and cannot send a message or change settings.

The vertical flow is ordinary open, controlled Unicode typing, BACK cancellation,
ordinary reopening with an empty new page generation, and final close. Each
consumed input has durable, text-free primitive intent before delivery. Native
normal-control originals and their actual request receipts bracket a separately
queried `NativeChatView` model/settings/actual-keyboard original. The full native
and host acquisition bracket stays below 1.5 seconds; source clocks retain their
original domain. Closed quiet requires three advancing observations spanning
three seconds on host epoch/monotonic, native epoch and native UI elapsed time.
QML keyboard requests do not populate actual keyboard visibility.

Lost input returns are resolved by new original observations only. A delivered
replacement can qualify without another replacement. An uncertain focus-only
type remains pending; the owner never reruns that recipe. Explicit `cleanup`
can close the owned page while retaining the failed action and reporting
`failed:true`. An interrupted read retains its queries and partial originals.
An uncertain original-file birth remains owned; missing original evidence is
never reconstructed. Pure `archive` reads the retained actual files and grants
no new current product or cleanup fact. Journals are retained after local close.

Results use `verifiedDraftAction` and local draft fields, not a complete common
Chat result. They establish no independent peer receipt, mixer recovery, typing
network drainage, native weak-object/process/SDK retirement, or whole-run cleanup.
The normal-control component source digest identifies its QML location, not
loaded QML bytes. Full active Script/QML ownership remains a separate join.

The shared 25-step Chat scenario still requires actual independent peer sending
and movement, authenticated evidence for all ten state fields, owned mixer-only
outage/recovery, three-second no-replay proof and exact private settings/history
restoration. Existing passive history exports cannot restore arbitrary private
history; normal Erase controls and a separately owned exact private snapshot are
still missing. This packet enables none of those capabilities.

Selected tests use actual private WAL/files, inode checks and the real original
decoders over explicitly modeled Qt, native keyboard, settings, clocks and input
boundaries. They do not establish physical iOS behavior or compiled execution.

The nine owner cases and one budget case pass in the 41-test archive/Chat
regression run (15.414 seconds). The explicit no-build selection is:

```bash
PYTHONPATH=.:tests/device:tests/device/self_tests:tests/device/ios/self_tests python3 -m unittest -v -f \
  test_ios_chat_draft_owner.ChatDraftOwnerTests \
  test_ios_chat_draft_owner.ChatDraftBudgetTests
```

The local run additionally used the private TMPDIR, no-build verification
overlay, bytecode suppression and a unique blocked-attempt log.

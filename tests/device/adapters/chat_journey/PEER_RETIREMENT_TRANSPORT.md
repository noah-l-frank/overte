# Restricted original peer retirement transport

`ChatPeerRetirementFiles` v1 is a fresh host transport over the original private
actor directory and unchanged actor-files v1 ledger. It does not create a new
native actor or native lifetime. Its constructor requires the completed original
`ChatPeerInputClose`, unchanged input/distance journals and immutable chunks,
actual absence of both original input paths and independent original receipt-FD
absence. The exact original peer lock must already be held.

The current original Inspect command must have a completely consumed matching
result before construction. Both original file bytes/stamps, original native-held
result/source descriptors, PID/start/executable guard and compiled SOURCE remain
qualified against the exact previously accepted original result. Its historical
native epoch is preserved and is never relabelled as a fresh sample; the next
operation must obtain a new native result. A pending command, previous unprocessed result,
closing ledger, replaced original resource or unknown input close is refused.
Construction does not publish another native command or adopt an incomplete
transaction. It preserves the original journal bytes.

The new transport acquires its own `OriginalDescriptor` for the same directory.
It neither replaces the original action transport nor copies/rebinds its old
phase callback. The parent may bind its actual cleanup fence to the new instance.
Only Inspect and Retire for the already owned run are allowed. The original input
close marker also prevents a new `ChatPeerInput` from reopening the input channel.
Every read, send and close rechecks the completed input authority and receipt-FD
absence. Only one successful new transport may be made from an original instance.

`OwnedChatPeer.retirement_cache(run, input_close)` uses this actual transport,
original peer kernel/source guards, exact peer lock and the existing original
capture/lifetime stores to construct a fresh `ChatCacheLifetime` reader. It does
not activate or retire the cache during construction. Its native requests retain
the original lifetime's once-only mutation IDs; a new native observation is still
required. Host detach closes only owned host descriptors. IPC close is always
retained, using the separately checked actual result-FD absence path; this API
cannot discard the original journal.

Focused checks use actual private files/host descriptor ownership and explicit
synthetic native/clock/receipt producer seams. They cover unchanged old callback,
new strict descriptor, actual original consumed transaction, retained IPC close,
unfinished/later-leaked input ownership, unprocessed commands and prohibited
Observe/foreign-run/reopened-input/discard routes. No product Agent, domain,
network peer or physical device is run. The whole parent still needs to join both
cache retirements, two independent final absence roles, original app process/Qt
release, post-restart physical profile checks and immutable final archive. This
transport alone grants no feature capability or hermetic AC build provenance.

```sh
cd tests/device
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest self_tests.test_chat_peer_retirement -v
```

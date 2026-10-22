# Original peer input closure v1

`ChatPeerInputClose` closes only an already released run's original peer input
command, receipt and actual native receipt descriptor. It does not retire the
Chat cache, observation IPC, native source/root, observer timer, subscription,
fixture process or any input/source/history journal. Full Chat remains partial.

The constructor requires the exact original `ChatPeerInput`, the actual native
Chat reader attached to its file transport, the same original peer source-lock
instance used by the distance owner, and a new private close journal. All input
transactions must be fully consumed with exactly one release and a native v3
release tombstone. Any original Hold additionally requires the exact completed
`ChatPeerDistant` whose sender owns that input object. Its immutable original
transcript, actual final return/motion observations and stopped poll counter
must match. A restore receipt alone provides no restoration authority. A run
that never held the peer does not need a position restoration proof.

The source lock stays held throughout closure. A new ordinary native Chat
Inspect obtains each optional original input-lifetime extension; the input
channel itself receives no Inspect or other command. Actual original owner run,
input birth, consumed sequence and script polls stay fixed. Actual Chat source
state/events also stay unchanged. The close owner observes three complete
seconds on both native and monotonic clocks before removal and another three
seconds after it. Consecutive original source epochs advance, with gaps at most
500 ms and each quiet window bounded by 20 seconds. Final original guards,
serialization, copying and journal writes stay within the sampled 1.5-second
freshness bound; frozen clocks or a slow final removal intent cannot qualify.

Every original native observation envelope is preserved byte for byte as a
base64 row with digest and original file stamp in immutable `ChatSourceChunks`.
A durable `reading` root precedes acquisition. Missing roots, orphan chunks,
reading or lost writes cannot be adopted as a new history. No source transcript
is truncated and no limits are raised.

Command and receipt each get a distinct durable removal intent. Immediately
before their single `unlink`, verify the original inode/full nanosecond stamp
and exact original command bytes or receipt digest, then original source guard
and clocks. Foreign replacements are retained. After the receipt disappears,
the existing native timer must actually close its original descriptor. Both new
native path/handle observations and the independent original Linux process FD
inventory must establish absence. An unlink response or source `open:false`
alone cannot complete closure. A late actual script poll after removal fails the
post-removal window without reopening the input files.

Once this close owner is admitted, all `ChatPeerInput.issue` calls sharing its
original file owner are blocked, including passive input Inspect. Reconstruction
cannot reopen the removed input files. Any failure permanently poisons this
owner. There is no second unlink, input retry, cold adoption, failure overwrite
or journal deletion. A lost removal receipt remains at its original durable
intent even if the path is already absent. Completed evidence also remains
retained for the enclosing whole-feature finalizer. `OwnedChatPeer.input_close`
constructs the owner with its exact original reader and lock.

Focused verification:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device python3 -m unittest self_tests.test_chat_peer_input_close -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device python3 tests/device/contracts/chat/test_chat_actor_input_lifetime_native.py -v
```

The native test compiles the complete original Qt5/POSIX actor producer and runs
only an owned stdin worker. The actual original Linux PID/start/executable and
FD inventory, real IPC files, source parser, close owner, two real-time quiet
windows and one-time original removals are exercised together. Avatar,
NodeList, network and assigned script are explicit seams; no Assignment Client,
product service, device or OpenXR runtime is executed. Component countercases
also cover pre/post-removal polls, retained deleted FDs despite reported closure,
lost receipts, foreign inodes, typed freshness and missing independent restore
proof. This is resource-scope evidence, not product peer or full Chat acceptance.

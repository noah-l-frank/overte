# Original independent Chat observer producer

`PicoChatCursorActor` version 1 runs only through the existing independently
provisioned Pico `feature_observer.py` entrypoint. Observer configuration version
3 adds `area=chat` and the exact private `peerConfig` file. Existing version 1
and 2 configurations keep their existing routes. No target discovery, product
process launch, installation, repair or controller input is added.

The producer waits for the original prepared Parent and passively acquires its
own `PicoChatWitness`, `OwnedChatPeer`, native readers and OS lock objects. The
legacy witness must have no publications or existing journal. Its original
initial and active sample owners supply the new global cursor and publisher;
the producer never publishes through the old witness. The normal completed
input journal authorizes stage selection. Cleanup uses a new final-absence
sample owner with the exact original code reader and lock instances.

The producer's fixed private `chat-cursor-actor-owner-*` root records a new
original instance, actual `/proc/self` PID/start/boot identity, bindings and
the two actual captured peer-directory/executable descriptor pairs. It pins
its physical root stamp, canonical cached value and pair descriptions across
each CAS. A cold root or rootless child is retained. It never becomes a fresh
producer by loading a ready-looking file.

The separate fixed `chat-cursor-actor-stop-*` command contains exactly:

```json
{
  "picoChatCursorActorStopVersion": 1,
  "commandId": "<32 lowercase hex>",
  "instance": "<the original producer instance>",
  "runId": "<the original run>",
  "afterSequence": 3,
  "ticket": "<the actual current cleanup publication ticket>"
}
```

`afterSequence` is the actual current global publication sequence, not a phase
count or caller offset. The producer accepts one original command only while
the Parent is `caches-retired`, the current stage is cleanup, and every actual
publication/query transaction has fully completed. It pins the command's exact
physical stamp and original bytes through stop, seal and closure. A mismatch,
lost CAS, failed original lock exit or unknown command quarantines the warm
producer without publication replay or command replacement.

After the durable `stop-issued` intent, the Actor constructs and runs its own
`ChatCursorSourceSeal`. It preserves the full returned original graph receipt.
After `host-close-issued`, it calls the actual `OriginalDescriptor.close` for
both captured pairs, then detaches the original witness wrappers and verifies
every original pair is closed with no lost/recycled half. The final durable
`host-closed` result has scope `original-independent-chat-host-handles`. It
retains the command, original source roots/chunks, seal and owner result for
the Parent's later complete archival. Best-effort `detach()` alone cannot
produce this result.

This is the producer side of the process boundary. Its host result does not
prove that the observer process has exited. The Parent still needs passive
acquisition of this exact originally live host PID/start/executable, the
original returned command/result, independent physical graph validation and
actual kernel absence after termination. The local v1 cleanup consumer still
requires live Actor objects in its own host process; it cannot adopt these
files as those objects. A separate explicit remote consumption join is needed.
The existing full archive diagnostic and in-process Actor scheduling seam do
not qualify this boundary. Public Chat capability remains disabled.

The five `self_tests.test_pico_chat_cursor_actor` cases execute the actual stage
selection, repeated publisher, full source seal and original Linux descriptor
closing bodies. Native producers, Parent provenance, the remaining 24 input
rows and initial object injection are explicit seams. Separate actual Pico
factory coverage passively acquires its own already-owned stdin peer and
checks captured pairs, cold refusal and host-only detach without changing the
durable publishing intent. Ten small observer tests preserve legacy routes,
validate the private v3 configuration and exercise the real loop routing and
deadline with model owners. No product App, AssignmentClient, device or
independent observer entrypoint process is launched by these tests.

The first six-case source/factory run completed in 32.609 seconds: all five
source cases passed, and the factory test failed because it expected the
internal error instead of the existing private factory wrapper's `ValueError`.
Only that test expectation was corrected. The two actual factory/retention
cases and ten observer cases then passed together, 12/12 in 5.435 seconds.
Those timings describe host checks, not native/device performance or a whole
feature result.
